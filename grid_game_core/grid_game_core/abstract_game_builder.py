from abc import abstractmethod
from typing import List, Tuple, Any, Dict
from django.db.models import Manager
from datetime import datetime
import logging

from .abstract_filters import BaseFilter, BaseFilterFactory

logger = logging.getLogger(__name__)


class BaseGameBuilder:
    """
    Abstract base class for game builders.
    
    This provides the common logic for building grid games across different domains.
    """
    
    def __init__(self, filter_factory: BaseFilterFactory, random_seed: int = 0):
        """
        Initialize the game builder.
        
        Args:
            filter_factory: Factory for creating filters
            random_seed: Random seed for deterministic behavior
        """
        self.filter_factory = filter_factory
        self.random_seed = random_seed
        self.min_num_results = 5
        self.max_num_results = 40
        self.max_tuning_attempts = 20
        self.num_statics = 3
        self.num_dynamics = 3
        
        # Define high-priority filters that should be selected more often
        self.high_priority_filters = {}
    
    @abstractmethod
    def get_entity_manager(self) -> Manager:
        """
        Get the Django manager for the entity model.
        
        Returns:
            Django manager for entities
        """
        pass
    
    @abstractmethod
    def get_game_filter_db_model(self):
        """
        Get the GameFilterDB model class.
        
        Returns:
            GameFilterDB model class
        """
        pass
    
    @abstractmethod
    def get_game_grid_model(self):
        """
        Get the GameGrid model class.
        
        Returns:
            GameGrid model class
        """
        pass
    
    def weighted_choice(self, items: List[Any], weights: List[float]) -> Any:
        """
        Make a weighted random choice from a list of items.
        
        Args:
            items: List of items to choose from
            weights: List of weights (higher weight = less likely to be selected)
            
        Returns:
            Randomly selected item based on weights
        """
        import random
        
        # Convert weights to probabilities (inverse of weights)
        total = sum(1.0 / w for w in weights)
        r = random.random() * total
        upto = 0
        
        for item, weight in zip(items, weights):
            upto += 1.0 / weight
            if upto > r:
                return item
        
        return items[-1]  # Fallback
    
    def get_filter_weights(self, filter_pool: List[BaseFilter], filter_type: str, days: int = 7) -> Dict[str, float]:
        """
        Calculate weights for filters based on recent usage.
        
        Args:
            filter_pool: List of available filters
            filter_type: 'static' or 'dynamic'
            days: Number of days to look back for usage
            
        Returns:
            Dict mapping filter class names to their weights
            
        TODO: Do not use `filter_obj.__class__.__name__` as a distrinction. There could be many filters with the same class name,
        but different configurations so they are very different in nature. Better add a `unique_filter_type` property to the filter class.
        """
        from datetime import timedelta
        
        # Get recent filter usage from GameFilterDB
        cutoff_date = datetime.now().date() - timedelta(days=days)
        GameFilterDB = self.get_game_filter_db_model()
        
        recent_usage = GameFilterDB.objects.filter(
            date__gte=cutoff_date,
            filter_type=filter_type
        )
        
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
                    filter_class=filter_class,
                    date__gte=datetime.now().date() - timedelta(days=2)
                ).count()
                if very_recent > 0:
                    weights[filter_class] += very_recent * 1.0
            
            # Adjust weight based on high priority filters
            if filter_class in self.high_priority_filters:
                weights[filter_class] = self.high_priority_filters[filter_class]
        
        return weights
    
    def select_filters(self, filter_pool: List[BaseFilter], num_filters: int, filter_type: str) -> List[BaseFilter]:
        """
        Select filters using weighted random choice based on recent usage.
        
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
    
    def tune_filter(self, dynamic_filter: BaseFilter, static_filters: List[BaseFilter], all_entities: Manager) -> Tuple[bool, BaseFilter]:
        """
        Tune a dynamic filter to get the right number of results.
        
        Args:
            dynamic_filter: The dynamic filter to tune
            static_filters: List of static filters to test against
            all_entities: Manager for all entities
            
        Returns:
            Tuple of (success, tuned_filter)
        """
        num_results = []
        success = True
        last_action = None
        
        for static_filter in static_filters:
            filtered_entities = static_filter.apply_filter(dynamic_filter.apply_filter(all_entities))
            num_results.append(len(filtered_entities))
            logger.debug(f"...filter [{static_filter.get_description()}] x [{dynamic_filter.get_description()}] returned {num_results[-1]} results")
        
        # If some results are higher than the max, but others are lower we can skip tuning
        if any(n > self.max_num_results for n in num_results) and any(n < self.min_num_results for n in num_results):
            logger.debug(f"...filter [{dynamic_filter.get_description()}] returned results out of range")
            return False, None
        
        # If one of the results is higher than the max, we need to narrow the filter
        if any(n > self.max_num_results for n in num_results):
            if last_action == 'widen':
                logger.debug(f"...filter [{dynamic_filter.get_description()}] is oscillating, giving up")
                return False, None
            dynamic_filter.narrow_filter()
            logger.debug(f"...narrowed filter to [{dynamic_filter.get_description()}]")
            last_action = 'narrow'
            success = False
        elif any(n < self.min_num_results for n in num_results):
            if last_action == 'narrow':
                logger.debug(f"...filter [{dynamic_filter.get_description()}] is oscillating, giving up")
                return False, None
            dynamic_filter.widen_filter()
            logger.debug(f"...widened filter to [{dynamic_filter.get_description()}]")
            last_action = 'widen'
            success = False
        
        return success, dynamic_filter
    
    def get_tuned_filters(self, requested_date: datetime, num_iterations: int = 10) -> Tuple[List[BaseFilter], List[BaseFilter]]:
        """
        Get or create tuned filters for a specific date.
        
        Args:
            requested_date: The date to get filters for
            num_iterations: Number of iterations to try generating filters
            
        Returns:
            Tuple of (static_filters, dynamic_filters)
        """
        # Check if filters already exist in database for today
        GameFilterDB = self.get_game_filter_db_model()
        existing_filters = GameFilterDB.objects.filter(date=requested_date)
        
        if existing_filters.exists():
            # Reconstruct filters from database
            static_filters = []
            dynamic_filters = []
            
            for db_filter in existing_filters.order_by('filter_index'):
                filter_obj = self.filter_factory.create_filter_from_config(
                    db_filter.filter_class,
                    db_filter.filter_config
                )
                if db_filter.filter_type == 'static':
                    static_filters.append(filter_obj)
                else:
                    dynamic_filters.append(filter_obj)
            
            if len(static_filters) == self.num_statics and len(dynamic_filters) == self.num_dynamics:
                # Ensure GameGrid exists for the requested date
                self.update_game_grid(requested_date, static_filters, dynamic_filters)
                return static_filters, dynamic_filters
        
        # If no filters exist or they're incomplete, generate new ones
        for loop_index in range(num_iterations):
            # Let's try to not use dynamic_filters in the row, as these tend to be more generic and not as interesting
            # We'll use them in later iterations if we cannot find a good grid with the static filters
            use_dynamic_filters_in_row = False
            if loop_index > num_iterations / 2:
                use_dynamic_filters_in_row = True
            
            static_filters, dynamic_filters = self.generate_grid(use_dynamic_filters_in_row=use_dynamic_filters_in_row)
            
            if len(dynamic_filters) < self.num_dynamics:
                logger.warning(f"Failed to generate a grid with {self.num_dynamics} dynamic filters. Static filters: {static_filters}")
                continue
            
            if len(static_filters) == self.num_statics:
                # Save filters to database
                for idx, filter_obj in enumerate(static_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type='static',
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=self.filter_factory.filter_to_json(filter_obj),
                        filter_index=idx
                    )
                
                for idx, filter_obj in enumerate(dynamic_filters):
                    GameFilterDB.objects.create(
                        date=requested_date,
                        filter_type='dynamic',
                        filter_class=filter_obj.__class__.__name__,
                        filter_config=self.filter_factory.filter_to_json(filter_obj),
                        filter_index=idx
                    )
                
                # Update game grid
                self.update_game_grid(requested_date, static_filters, dynamic_filters)
                return static_filters, dynamic_filters
        
        # If we get here, we failed to generate a good grid
        logger.error(f"Failed to generate a good grid after {num_iterations} iterations")
        return [], []
    
    def generate_grid(self, use_dynamic_filters_in_row: bool = False) -> Tuple[List[BaseFilter], List[BaseFilter]]:
        """
        Generate a grid of filters.
        
        Args:
            use_dynamic_filters_in_row: Whether to use dynamic filters in rows
            
        Returns:
            Tuple of (static_filters, dynamic_filters)
        """
        # Get filters for rows using weighted selection
        dynamic_filters = self.filter_factory.get_dynamic_filters(self.random_seed)
        static_filters = self.filter_factory.get_static_filters(self.random_seed)
        
        # Select filters
        selected_dynamic = self.select_filters(dynamic_filters, self.num_dynamics, 'dynamic')
        selected_static = self.select_filters(static_filters, self.num_statics, 'static')
        
        # Tune dynamic filters
        all_entities = self.get_entity_manager()
        tuned_dynamic = []
        
        for dynamic_filter in selected_dynamic:
            success, tuned_filter = self.tune_filter(dynamic_filter, selected_static, all_entities)
            if success:
                tuned_dynamic.append(tuned_filter)
            else:
                # Try a few more times with different tuning
                for attempt in range(self.max_tuning_attempts):
                    success, tuned_filter = self.tune_filter(dynamic_filter, selected_static, all_entities)
                    if success:
                        tuned_dynamic.append(tuned_filter)
                        break
        
        return selected_static, tuned_dynamic
    
    def update_game_grid(self, date: datetime, static_filters: List[BaseFilter], dynamic_filters: List[BaseFilter]):
        """
        Update the game grid with filter information.
        
        Args:
            date: The date for the grid
            static_filters: List of static filters
            dynamic_filters: List of dynamic filters
        """
        GameGrid = self.get_game_grid_model()
        all_entities = self.get_entity_manager()
        
        # Calculate correct entities for each cell
        cell_correct_entities = {}
        
        for row_idx, dynamic_filter in enumerate(dynamic_filters):
            for col_idx, static_filter in enumerate(static_filters):
                cell_key = f'{row_idx}_{col_idx}'
                filtered_entities = static_filter.apply_filter(dynamic_filter.apply_filter(all_entities))
                cell_correct_entities[cell_key] = len(filtered_entities)
        
        # Create or update the game grid
        game_grid, created = GameGrid.objects.get_or_create(
            date=date,
            defaults={
                'grid_size': 3,
                'cell_correct_entities': cell_correct_entities
            }
        )
        
        if not created:
            game_grid.cell_correct_entities = cell_correct_entities
            game_grid.save() 