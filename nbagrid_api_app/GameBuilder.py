import logging
import random
from datetime import datetime, timedelta

from django.db.models import Manager

from nbagrid_api_app.GameFilter import GameFilter, create_filter_from_db, get_dynamic_filters, get_static_filters
from nbagrid_api_app.models import GameFilterDB, GameGrid, Player

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GameBuilder(object):
    def __init__(self, random_seed: int = 0):
        self.random_seed = random_seed
        self.dynamic_filters = get_dynamic_filters(self.random_seed)
        self.static_filters = get_static_filters(self.random_seed)
        self.min_num_results = 5
        self.max_num_results = 40
        self.max_tuning_attempts = 20
        self.num_statics = 3
        self.num_dynamics = 3

        # Define high-priority filters that should be selected more often
        self.high_priority_filters = {
            "TeamFilter": 0.1,  # TeamFilter is almost always selected
            "PositionFilter": 1.0,  # PositionFilter is unaffected by last usage
        }

    def weighted_choice(self, items, weights):
        """Make a weighted random choice from a list of items.

        Args:
            items: List of items to choose from
            weights: List of weights (higher weight = less likely to be selected)

        Returns:
            Randomly selected item based on weights
        """
        # Convert weights to probabilities (inverse of weights)
        total = sum(1.0 / w for w in weights)
        r = random.random() * total
        upto = 0
        for item, weight in zip(items, weights):
            upto += 1.0 / weight
            if upto > r:
                return item
        return items[-1]  # Fallback

    def get_filter_weights(self, filter_pool, filter_type, days=7):
        """Calculate weights for filters based on recent usage from GameFilterDB.

        Args:
            filter_pool: List of available filters
            filter_type: 'static' or 'dynamic'
            days: Number of days to look back for usage

        Returns:
            Dict mapping filter class names to their weights (higher weight = less likely to be selected)
        """
        # Get recent filter usage from GameFilterDB
        cutoff_date = datetime.now().date() - timedelta(days=days)
        recent_usage = GameFilterDB.objects.filter(date__gte=cutoff_date, filter_type=filter_type)

        weights = {}

        # Initialize weights for all filters
        for filter_obj in filter_pool:
            filter_class = filter_obj.__class__.__name__
            weights[filter_class] = 1.0  # Base weight

            # Count recent usage
            usage_count = recent_usage.filter(filter_class=filter_class).count()
            if usage_count > 0:
                # Increase weight based on usage (more usage = higher weight = less likely to be selected)
                weights[filter_class] += usage_count * 0.5

                # Add extra weight for very recent usage (last 2 days)
                very_recent = recent_usage.filter(
                    filter_class=filter_class, date__gte=datetime.now().date() - timedelta(days=2)
                ).count()
                if very_recent > 0:
                    weights[filter_class] += very_recent * 1.0

            # Adjust weight based on high priority filters
            if filter_class in self.high_priority_filters:
                weights[filter_class] = self.high_priority_filters[filter_class]

        return weights

    def select_filters(self, filter_pool, num_filters, filter_type):
        """Select filters using weighted random choice based on recent usage.

        Args:
            filter_pool: List of available filters
            num_filters: Number of filters to select
            filter_type: 'static' or 'dynamic'

        Returns:
            List of selected filters
        """
        # Get filter weights based on recent usage
        weights = self.get_filter_weights(filter_pool, filter_type)

        # Convert weights to list matching filter_pool order
        weight_list = [weights[f.__class__.__name__] for f in filter_pool]

        # Select filters using weighted random choice
        selected_filters = []
        available_filters = filter_pool.copy()
        available_weights = weight_list.copy()

        for _ in range(num_filters):
            if not available_filters:
                break

            selected = self.weighted_choice(available_filters, available_weights)
            selected_filters.append(selected)

            # Remove selected filter from available options
            idx = available_filters.index(selected)
            available_filters.pop(idx)
            available_weights.pop(idx)

        return selected_filters

    def tune_filter(self, dynamic_filter: GameFilter, static_filters: list[GameFilter], all_players: Manager[Player]):
        num_results = []
        success = True
        last_action = None
        for static_filter in static_filters:
            num_results.append(len(static_filter.apply_filter(dynamic_filter.apply_filter(all_players))))
            logger.debug(
                f"...filter [{static_filter.get_desc()}] x [{dynamic_filter.get_desc()}] returned {num_results[-1]} results"
            )

        # if some results are higher than the max, but others are lower we can skip tuning
        if any(n > self.max_num_results for n in num_results) and any(n < self.min_num_results for n in num_results):
            logger.debug(f"...filter [{dynamic_filter.get_desc()}] returned results out of range")
            return (False, None)

        # if one of the results is higher than the max, we need to narrow the filter
        if any(n > self.max_num_results for n in num_results):
            if last_action == "widen":
                logger.debug(f"...filter [{dynamic_filter.get_desc()}] is oscillating, giving up")
                return (False, None)
            dynamic_filter.narrow_filter()
            logger.debug(f"...narrowed filter to [{dynamic_filter.get_desc()}]")
            last_action = "narrow"
            success = False
        elif any(n < self.min_num_results for n in num_results):
            if last_action == "narrow":
                logger.debug(f"...filter [{dynamic_filter.get_desc()}] is oscillating, giving up")
                return (False, None)
            dynamic_filter.widen_filter()
            logger.debug(f"...widened filter to [{dynamic_filter.get_desc()}]")
            last_action = "widen"
            success = False
        return (success, dynamic_filter)

    def get_tuned_filters(self, requested_date, num_iterations: int = 10):
        # Check if filters already exist in database for today
        existing_filters = GameFilterDB.objects.filter(date=requested_date)

        if existing_filters.exists():
            # Reconstruct filters from database
            static_filters = []
            dynamic_filters = []

            for db_filter in existing_filters.order_by("filter_index"):
                filter_obj = create_filter_from_db(db_filter)
                if db_filter.filter_type == "static":
                    static_filters.append(filter_obj)
                else:
                    dynamic_filters.append(filter_obj)

            if len(static_filters) == self.num_statics and len(dynamic_filters) == self.num_dynamics:
                # Ensure GameGrid exists for the requested date
                self.update_game_grid(requested_date, static_filters, dynamic_filters)
                return (static_filters, dynamic_filters)

        # If no filters exist or they're incomplete, generate new ones
        for loop_index in range(num_iterations):

            # Let's try to not use dynamic_filters in the row, as these tend to be more generic and not as interesting
            # We'll use them in later iterations if we cannot find a good grid with the static filters
            use_dynamic_filters_in_row = False
            if loop_index > num_iterations / 2:
                use_dynamic_filters_in_row = True
            static_filters, dynamic_filters = self.generate_grid(use_dynamic_filters_in_row=use_dynamic_filters_in_row)
            if len(dynamic_filters) < self.num_dynamics:
                logger.warning(
                    f"Failed to generate a grid with {self.num_dynamics} dynamic filters. Static filters: {static_filters}"
                )
                continue
            if len(static_filters) == self.num_statics:
                # Save filters to database
                for idx, filter_obj in enumerate(static_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type="static",
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=filter_obj.__dict__,
                        filter_index=idx,
                    )

                for idx, filter_obj in enumerate(dynamic_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type="dynamic",
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=filter_obj.__dict__,
                        filter_index=idx,
                    )

                # Create/update the GameGrid for this date
                self.update_game_grid(requested_date, static_filters, dynamic_filters)

                return (static_filters, dynamic_filters)
        raise Exception(
            f"Failed to generate a grid with {self.num_dynamics} dynamic filters and {self.num_statics} static filters"
        )

    def update_game_grid(self, date, static_filters, dynamic_filters):
        """
        Create or update the GameGrid for the specified date with calculated player counts

        Args:
            date: The game date
            static_filters: The static filters (rows)
            dynamic_filters: The dynamic filters (columns)
        """
        # Create or get the GameGrid for this date
        game_grid, created = GameGrid.objects.get_or_create(
            date=date, defaults={"grid_size": self.num_statics}  # Assuming grid_size is the number of rows
        )

        # Get all players
        all_players = Player.objects.all()

        # Calculate cell player counts
        cell_stats = {}

        # For each cell in the grid (row x column)
        for row_idx, row_filter in enumerate(static_filters):
            for col_idx, col_filter in enumerate(dynamic_filters):
                cell_key = f"{row_idx}_{col_idx}"

                # Apply both filters to get players that match this cell
                matching_players = row_filter.apply_filter(col_filter.apply_filter(all_players))

                # Store the count of matching players
                cell_stats[cell_key] = matching_players.count()

                logger.debug(f"Cell {cell_key}: {cell_stats[cell_key]} matching players")

        # Update the GameGrid with all calculated stats at once
        game_grid.cell_correct_players = cell_stats
        game_grid.save()

        logger.info(f"Updated GameGrid for {date} with correct player counts: {cell_stats}")

        return game_grid

    def generate_grid(self, use_dynamic_filters_in_row: bool = False):
        # Get filters for rows using weighted selection
        row_filter_pool = self.static_filters
        if use_dynamic_filters_in_row:
            row_filter_pool += self.dynamic_filters
        row_filters = self.select_filters(row_filter_pool, self.num_statics, "static")
        column_filters = []

        # Go through the list of dynamic filters and tune them to the static filters
        # Randomize the order of dynamic filters before iteration
        all_players = Player.objects.all()
        for column_filter in random.sample(self.dynamic_filters, len(self.dynamic_filters)):
            # Do not use the same dynamic filter twice
            curr_filter_name = column_filter.__class__.__name__
            if column_filter in column_filters:
                continue
            if column_filter in row_filters:
                continue

            num_tuning_attempts = 0
            found_filter = False
            while num_tuning_attempts < self.max_tuning_attempts:
                success, column_filter = self.tune_filter(column_filter, row_filters, all_players)
                if column_filter is None:
                    break
                if success:
                    column_filters.append(column_filter)
                    found_filter = True
                    break
                num_tuning_attempts += 1
            # Continue with the next dynamic filter if we did not find a suitable filter
            if not found_filter:
                logger.warning(
                    f"Failed to tune filter {curr_filter_name}. Filters: ['{row_filters[0].get_desc()}'] and ['{row_filters[1].get_desc()}'] and ['{row_filters[2].get_desc()}']"
                )
                continue
            # Check if we already have the required number of dynamic filters
            if len(column_filters) == self.num_dynamics:
                break

        return (row_filters, column_filters)
