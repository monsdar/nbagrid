import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import json
import random
import re
from datetime import datetime, timedelta

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from nbagrid_api_app.auth import basic_auth_required
from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.GameFilter import GameFilter
from nbagrid_api_app.GameState import CellData, GameState
from nbagrid_api_app.metrics import (
    increment_active_games,
    increment_unique_users,
    record_game_completion,
    record_game_start,
    record_user_guess,
    record_wrong_guess,
    track_request_latency,
    update_active_games,
    update_pythonanywhere_cpu_metrics,
    update_total_guesses_gauge,
)
from nbagrid_api_app.models import GameCompletion, GameFilterDB, GameGrid, GameResult, GridMetadata, ImpressumContent, LastUpdated, Player, UserData


def get_valid_date(year, month, day):
    """Validate and return a valid date for the game."""
    current_date = datetime.now()
    requested_date = datetime(year=year, month=month, day=day)
    earliest_date = datetime(2025, 4, 1)

    if requested_date > current_date:
        return current_date
    if requested_date < earliest_date:
        return earliest_date
    return requested_date


def get_navigation_dates(requested_date: datetime) -> tuple[datetime, datetime, bool, bool]:
    """Calculate previous and next dates for navigation."""
    prev_date: datetime = requested_date - timedelta(days=1)
    next_date: datetime = requested_date + timedelta(days=1)
    earliest_date: datetime = datetime(2025, 4, 1)

    show_prev = prev_date >= earliest_date
    show_next = next_date <= datetime.now()

    return prev_date, next_date, show_prev, show_next

def get_random_past_game_filters(requested_date: datetime, builder: GameBuilder) -> tuple[list[GameFilter], list[GameFilter]]:
    """Final fallback method to copy a random past game when no cached games are available."""
    logger.warning(f"No cached games available for fallback. Attempting to copy random past game for {requested_date}.")
    
    # Find any existing game from the past (any date that has GameFilterDB entries)
    past_game_dates = GameFilterDB.objects.values_list('date', flat=True).order_by('date')
    
    if past_game_dates.exists():
        # Select a random past game date
        import random
        random_past_date = random.choice(past_game_dates)
        logger.info(f"Copying random past game from {random_past_date} to {requested_date}")
        
        # Copy GameFilterDB entries to the new date
        past_filters = GameFilterDB.objects.filter(date=random_past_date)
        for past_filter in past_filters:
            GameFilterDB.objects.create(
                date=requested_date,
                filter_type=past_filter.filter_type,
                filter_class=past_filter.filter_class,
                filter_config=past_filter.filter_config,
                filter_index=past_filter.filter_index,
            )
        
        # NOTE: Do not copy GridMetadata if it exists, let's keep the copied game "anonymous" by not adding a name to it
        
        # Copy GameGrid if it exists
        try:
            past_game_grid = GameGrid.objects.filter(date=random_past_date).first()
            if past_game_grid:
                GameGrid.objects.create(
                    date=requested_date,
                    grid_size=past_game_grid.grid_size,
                    cell_correct_players=past_game_grid.cell_correct_players,
                )
        except Exception as grid_error:
            logger.warning(f"Failed to copy GameGrid: {grid_error}")
        
        # Now try to get the filters from the copied past game
        try:
            filters = builder.get_filters_from_db(requested_date)
            if filters[0] and filters[1]:
                logger.info(f"Successfully copied random past game filters for {requested_date}")
                return filters
            else:
                raise Exception("Failed to retrieve copied past game filters")
        except Exception as copy_error:
            logger.error(f"Copying past game also failed: {copy_error}")
            raise Exception(f"All fallback methods failed, cannot generate filters for {requested_date}")
    else:
        # No games exist at all - this should be very rare
        logger.error(f"No games exist in the database at all. Cannot provide fallback.")
        raise Exception(f"No games exist in the database. Cannot provide fallback.")

def get_game_filters(requested_date: datetime) -> tuple[list[GameFilter], list[GameFilter]]:
    """Get or create game filters for the requested date."""
    # Create a GameBuilder with the requested date's timestamp as seed
    builder = GameBuilder(requested_date.timestamp())
    
    try:
        # Get the filters - this will either retrieve from DB or create new ones
        filters = builder.get_tuned_filters(requested_date, num_iterations=10, reuse_cached_game=True)
    except Exception as e:
        filters = get_random_past_game_filters(requested_date, builder) # Last resort, simply copy a random past game

    # Initialize scores for all cells if this is a new game and no completions exist
    # AND no initial game results exist for this date
    if (
        not GameCompletion.objects.filter(date=requested_date.date()).exists()
        and not GameResult.objects.filter(date=requested_date.date()).exists()
    ):
        static_filters, dynamic_filters = filters
        for row in range(len(dynamic_filters)):
            for col in range(len(static_filters)):
                cell_key = f"{row}_{col}"
                init_filters = [dynamic_filters[row], static_filters[col]]
                GameResult.initialize_scores_from_recent_games(
                    requested_date.date(), cell_key, filters=init_filters, game_factor=3
                )
    return filters


def initialize_game_state(request, year, month, day) -> tuple[str, GameState]:
    """Initialize or get the current game state from session."""
    game_state_key = f"game_state_{year}_{month}_{day}"
    game_state_dict = request.session.get(game_state_key, {})
    game_state = GameState().from_dict(game_state_dict)

    # Save the session if it's a new game state
    if game_state_key not in request.session:
        request.session[game_state_key] = game_state.to_dict()
        request.session.save()
    return game_state_key, game_state


def build_grid(static_filters: list[GameFilter], dynamic_filters: list[GameFilter]) -> list[list[dict]]:
    """Build the game grid with correct row/column structure."""
    grid = []
    for row_idx, dynamic in enumerate(dynamic_filters):
        row = []
        for col_idx, static in enumerate(static_filters):
            cell = {"filters": [static, dynamic], "row": row_idx, "col": col_idx}
            row.append(cell)
        grid.append(row)
    return grid


def get_game_stats(requested_date):
    """Get common game statistics for a given date."""
    return {
        "completion_count": GameCompletion.get_completion_count(requested_date.date()),
        "total_guesses": GameResult.get_total_guesses(requested_date.date()),
        "user_guesses": GameResult.get_total_user_guesses(requested_date.date()),
        "wrong_guesses": GameResult.get_total_wrong_guesses(requested_date.date()),
        "perfect_games": GameCompletion.get_perfect_games(requested_date.date()),
        "average_score": GameCompletion.get_average_score(requested_date.date()),
    }


def get_user_data(request):
    """Get or create user data for the current session."""
    try:
        user_data = UserData.get_or_create_user(request.session.session_key)
        logger.info(
            f"Created/retrieved UserData for session {request.session.session_key} with display name {user_data.display_name}"
        )
        return user_data
    except Exception as e:
        logger.error(f"Failed to create UserData: {e}")
        return None


def handle_game_completion(request, requested_date, game_state, correct_cells_count):
    """Handle game completion logic."""
    if not GameCompletion.objects.filter(date=requested_date.date(), session_key=request.session.session_key).exists():
        GameCompletion.objects.create(
            date=requested_date.date(),
            session_key=request.session.session_key,
            correct_cells=correct_cells_count,
            final_score=game_state.total_score,
        )

        # Create UserData for first-time game completion
        try:
            user_data = UserData.get_or_create_user(request.session.session_key)
            logger.info(
                f"Created/retrieved UserData for session {request.session.session_key} with display name {user_data.display_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create UserData: {e}")

        # Record game completion metrics
        result = "win" if correct_cells_count >= 9 else "lose"
        record_game_completion(game_state.total_score, result)
        return True
    return False


def get_ranking_data(requested_date, session_key):
    """Get ranking data for the current user."""
    streak, streak_rank, total_completions = GameCompletion.get_current_streak(session_key, requested_date.date())
    streak_rank = (streak_rank, total_completions) if streak > 0 else None
    ranking_data = GameCompletion.get_ranking_with_neighbors(requested_date.date(), session_key)
    return streak, streak_rank, ranking_data


def get_player_stats(session_key):
    """Get player statistics including total completions, perfect completions, and streaks."""
    try:
        # Get total completions and perfect completions
        total_completions = GameCompletion.objects.filter(session_key=session_key).count()
        perfect_completions = GameCompletion.objects.filter(session_key=session_key, correct_cells=9).count()

        # Get current completion streak
        current_streak = 0
        perfect_streak = 0
        latest_completion = GameCompletion.objects.filter(session_key=session_key).order_by("-date").first()
        if latest_completion:
            current_streak = latest_completion.completion_streak
            # Only show perfect streak if the latest completion was perfect
            if latest_completion.correct_cells == 9:
                perfect_streak = latest_completion.perfect_streak
            else:
                perfect_streak = 0

        return {
            "total_completions": total_completions,
            "perfect_completions": perfect_completions,
            "current_streak": current_streak,
            "perfect_streak": perfect_streak,
        }
    except Exception as e:
        logger.error(f"Error getting player stats: {e}")
        return {"total_completions": 0, "perfect_completions": 0, "current_streak": 0, "perfect_streak": 0}


def get_unplayed_game_data(session_key, current_date=None):
    """Get data about the first unplayed game for a user."""
    try:
        unplayed_date, has_unplayed_games = GameCompletion.get_first_unplayed_game(session_key, current_date)

        if has_unplayed_games and unplayed_date:
            return {
                "has_unplayed_games": True,
                "unplayed_date": unplayed_date,
                "unplayed_date_str": unplayed_date.strftime("%Y-%m-%d"),
                "unplayed_date_display": unplayed_date.strftime("%B %d, %Y"),
            }
        else:
            return {
                "has_unplayed_games": False,
                "unplayed_date": None,
                "unplayed_date_str": None,
                "unplayed_date_display": None,
            }
    except Exception as e:
        logger.error(f"Error getting unplayed game data: {e}")
        return {"has_unplayed_games": False, "unplayed_date": None, "unplayed_date_str": None, "unplayed_date_display": None}


def handle_player_guess(request, game_grid, game_state: GameState, requested_date: datetime):
    """Handle a player's guess."""
    if game_state.is_finished or game_state.attempts_remaining <= 0:
        logger.error(f"Cannot handle another guess: Game is already finished or attempts remaining is 0")
        return JsonResponse({"error": "Game is finished"}, status=400)

    try:
        # Get data from request.POST instead of request.body
        player_id = request.POST.get("player_id")
        row = int(request.POST.get("row", 0))
        col = int(request.POST.get("col", 0))
        cell_key = f"{row}_{col}"

        # Check if this cell already has a correct guess
        cell_data_list = game_state.selected_cells.get(cell_key, [])
        if any(cell_data["is_correct"] for cell_data in cell_data_list):
            logger.error(f"Cannot handle another guess:Cell {cell_key} already has a correct guess")
            return JsonResponse({"error": "Cell already correct"}, status=400)

        # check if player exists, we need it later
        try:
            player = Player.objects.get(stats_id=player_id)
        except Player.DoesNotExist:
            logger.error(f"Cannot handle guess: Player {player_id} not found")
            return JsonResponse({"error": "Player not found"}, status=404)

        cell = game_grid[row][col]
        is_correct = all(f.apply_filter(Player.objects.filter(stats_id=player_id)).exists() for f in cell["filters"])

        # Create new cell data for this guess
        cell_data = CellData(player_id=player_id, player_name=player.name, is_correct=is_correct)

        # Add the guess to the cell's data list
        if cell_key not in game_state.selected_cells:
            game_state.selected_cells[cell_key] = []
        game_state.selected_cells[cell_key].append(cell_data)

        # Handle correct guess
        if is_correct:
            handle_correct_guess(requested_date, cell_key, player, cell_data, game_state)
        else:
            # Record wrong guess in the database
            GameResult.record_wrong_guess(requested_date.date(), cell_key, player)
            # Record metrics for wrong guess
            date_str = requested_date.date().isoformat()
            record_wrong_guess(date_str)

        # Calculate total score for both correct and incorrect guesses
        update_total_score(game_state, requested_date)
        logger.info(
            f"Player {player.name} in cell {cell_key} guessed {'correctly' if is_correct else 'incorrectly'}. Total score: {game_state.total_score}"
        )

        game_state.decrement_attempts()
        game_state.check_completion(len(game_grid) * len(game_grid[0]))

        # If game is finished, get correct players for all remaining cells
        cell_players = {}
        game_completed = False
        if game_state.is_finished:
            cell_players = get_correct_players(game_grid, game_state)

            # Count how many cells have correct guesses
            correct_cells_count = sum(
                1
                for cell_key, cell_data_list in game_state.selected_cells.items()
                if any(cell_data.get("is_correct", False) for cell_data in cell_data_list)
            )

            # Handle game completion
            game_completed = handle_game_completion(request, requested_date, game_state, correct_cells_count)

        # Save the updated game state to the session
        game_state_key = f"game_state_{requested_date.year}_{requested_date.month}_{requested_date.day}"
        request.session[game_state_key] = game_state.to_dict()
        request.session.save()

        # Get stats data
        stats = get_game_stats(requested_date)

        # Get ranking data if game is finished
        streak, streak_rank, ranking_data = (
            get_ranking_data(requested_date, request.session.session_key) if game_state.is_finished else (0, None, None)
        )

        # Get player stats
        player_stats = get_player_stats(request.session.session_key)

        # Get updated unplayed game data if game is finished
        unplayed_game_data = None
        if game_state.is_finished:
            unplayed_game_data = get_unplayed_game_data(request.session.session_key, requested_date.date())

        return JsonResponse(
            {
                "is_correct": is_correct,
                "player_name": player.name,
                "cell_data": game_state.selected_cells[cell_key],
                "attempts_remaining": game_state.attempts_remaining,
                "is_finished": game_state.is_finished,
                "total_score": game_state.total_score,
                "cell_players": cell_players,
                "completion_count": stats["completion_count"],
                "total_guesses": stats["total_guesses"],
                "perfect_games": stats["perfect_games"],
                "average_score": stats["average_score"],
                "streak": streak,
                "streak_rank": streak_rank,
                "selected_cells": {k: [cd for cd in v] for k, v in game_state.selected_cells.items()},
                "ranking_data": ranking_data,
                "player_stats": player_stats,
                "unplayed_game_data": unplayed_game_data,
            }
        )
    except Exception as e:
        logger.error(f"Error handling guess: {e}")
        return JsonResponse({"error": "Server error"}, status=500)


def handle_correct_guess(requested_date, cell_key, player, cell_data, game_state):
    """Handle the logic for a correct guess."""
    try:
        result, created = GameResult.objects.get_or_create(
            date=requested_date.date(), cell_key=cell_key, player=player, defaults={"guess_count": 1, "initial_guesses": 0}
        )

        if not created:
            result.guess_count = result.guess_count + 1
            result.save()

        cell_score = GameResult.get_player_rarity_score(requested_date.date(), cell_key, player)
        cell_data["score"] = cell_score

        # Check if this is the first time this player has been guessed in this cell
        is_first_guess = result.guess_count == 1

        if is_first_guess:
            cell_data["tier"] = "first"
        elif cell_score < 0.80:
            cell_data["tier"] = "common"
        elif cell_score < 0.95:
            cell_data["tier"] = "rare"
        else:
            cell_data["tier"] = "epic"

        # Update the cell data in game_state
        game_state.selected_cells[cell_key].append(cell_data)

        # Record metrics for user guess
        date_str = requested_date.date().isoformat()
        record_user_guess(date_str)

        logger.info(
            f"Player {player.name} in cell {cell_key} - First guess: {is_first_guess}, Score: {cell_score}, Tier: {cell_data['tier']}"
        )
    except Exception as e:
        logger.error(f"Failed to store game result: {e}")


def update_total_score(game_state, requested_date):
    """Calculate the total score for all correct cells."""
    total_score = 0
    for cell_key, cell_data_list in game_state.selected_cells.items():
        correct_cell_data = next((cell_data for cell_data in cell_data_list if cell_data.get("is_correct", False)), None)
        if correct_cell_data:
            total_score += correct_cell_data["score"]
    game_state.total_score = total_score


def index(request):
    """Render today's game directly."""
    timer_stop = track_request_latency("index")
    try:
        current_date = datetime.now()
        return game(request, current_date.year, current_date.month, current_date.day)
    finally:
        timer_stop()


def get_correct_players(game_grid, game_state):
    """Get the correct players for each cell."""
    correct_players = {}
    for row in range(len(game_grid)):
        for col in range(len(game_grid[0])):
            cell_key = f"{row}_{col}"
            cell_data_list = game_state.selected_cells.get(cell_key, [])
            cell = game_grid[row][col]

            # Initialize the list for this cell
            correct_players[cell_key] = []

            # Add wrong guesses first
            for cell_data in cell_data_list:
                if not cell_data["is_correct"]:
                    try:
                        wrong_player = Player.objects.get(stats_id=cell_data["player_id"])
                        correct_players[cell_key].append(
                            {
                                "name": wrong_player.name,
                                "stats": [f.get_player_stats_str(wrong_player) for f in cell["filters"]],
                                "is_wrong_guess": True,
                            }
                        )
                    except Player.DoesNotExist:
                        pass

            # Add correct players
            matching_players = Player.objects.all()
            for f in cell["filters"]:
                matching_players = f.apply_filter(matching_players)
            # Include player stats for each matching player
            for p in matching_players:
                correct_players[cell_key].append(
                    {"name": p.name, "stats": [f.get_player_stats_str(p) for f in cell["filters"]], "is_wrong_guess": False}
                )

    return correct_players


def game(request, year, month, day):
    """Main game view function."""
    timer_stop = track_request_latency("game")
    try:
        requested_date = get_valid_date(year, month, day)
        # redirect to a valid date if the requested date is not valid
        if requested_date != datetime(year=year, month=month, day=day):
            return redirect("game", year=requested_date.year, month=requested_date.month, day=requested_date.day)

        # Get game title from GridMetadata if it exists
        try:
            grid_metadata = GridMetadata.objects.get(date=requested_date.date())
            game_title = grid_metadata.game_title
        except GridMetadata.DoesNotExist:
            game_title = None

        # Track unique users based on session key
        if not request.session.get("user_counted", False):
            request.session["user_counted"] = True
            request.session.save()
            increment_unique_users()
            logger.info(f"New unique user counted with session key: {request.session.session_key}")

        # Get user data
        user_data = get_user_data(request)

        prev_date, next_date, show_prev, show_next = get_navigation_dates(requested_date)
        static_filters, dynamic_filters = get_game_filters(requested_date)
        game_state_key, game_state = initialize_game_state(request, year, month, day)

        game_grid = build_grid(static_filters, dynamic_filters)

        if request.method == "POST":
            response = handle_player_guess(request, game_grid, game_state, requested_date)
            request.session[game_state_key] = game_state.to_dict()
            return response

        # Get correct players for each cell
        correct_players = get_correct_players(game_grid, game_state)

        # Get stats data
        stats = get_game_stats(requested_date)

        # Get the last update timestamp for player data
        try:
            last_updated = LastUpdated.objects.filter(data_type="player_data").order_by("-last_updated").first()
            last_updated_date = last_updated.last_updated if last_updated else None
        except Exception as e:
            logger.error(f"Error fetching last update timestamp: {e}")
            last_updated_date = None

        # Format the last updated date
        last_updated_str = last_updated_date.strftime("%B %d, %Y") if last_updated_date else "Unknown"

        # Track active games with per-date tracking
        date_str = requested_date.date().isoformat()
        if not request.session.get("tracked_games", {}):
            request.session["tracked_games"] = {}

        tracked_games = request.session.get("tracked_games", {})
        if date_str not in tracked_games:
            tracked_games[date_str] = True
            request.session["tracked_games"] = tracked_games
            request.session.save()

            # Increment active games counter
            increment_active_games()

            # Record a new game start
            record_game_start()
            logger.info(f"New game started for date {date_str} with session key: {request.session.session_key}")

        # Get ranking data if game is finished
        streak, streak_rank, ranking_data = (
            get_ranking_data(requested_date, request.session.session_key) if game_state.is_finished else (0, None, None)
        )

        # Get player stats
        player_stats = get_player_stats(request.session.session_key)

        # Get unplayed game data
        unplayed_game_data = get_unplayed_game_data(request.session.session_key, requested_date.date())

        # Check if impressum should be shown based on environment variable
        show_impressum = settings.NBAGRID_SHOW_IMPRESSUM

        return render(
            request,
            "game.html",
            {
                "year": year,
                "month": requested_date.strftime("%B"),
                "month_num": requested_date.month,
                "day": day,
                "game_title": game_title,
                "static_filters": [f.get_desc() for f in static_filters],
                "dynamic_filters": [f.get_desc() for f in dynamic_filters],
                "static_filters_detailed": [f.get_detailed_desc() for f in static_filters],
                "dynamic_filters_detailed": [f.get_detailed_desc() for f in dynamic_filters],
                "grid": game_grid,
                "selected_players": set(),
                "attempts_remaining": game_state.attempts_remaining,
                "selected_cells": game_state.selected_cells,
                "is_finished": game_state.is_finished,
                "correct_players": correct_players,
                "total_score": game_state.total_score,
                "completion_count": stats["completion_count"],
                "total_guesses": stats["total_guesses"],
                "perfect_games": stats["perfect_games"],
                "average_score": stats["average_score"],
                "streak": streak,
                "streak_rank": streak_rank,
                "show_prev": show_prev,
                "show_next": show_next,
                "prev_date": prev_date,
                "next_date": next_date,
                "last_updated_date": last_updated_str,
                "ranking_data": ranking_data,
                "user_data": user_data,
                "player_stats": player_stats,
                "unplayed_game_data": unplayed_game_data,
                "show_impressum": show_impressum,
            },
        )
    finally:
        timer_stop()


def search_players(request):
    """Search for players by name."""
    name = request.GET.get("name", "")
    if len(name) < 3:
        return JsonResponse([], safe=False)

    players = Player.objects.filter(name__icontains=name)[:5]
    return JsonResponse([{"stats_id": player.stats_id, "name": player.name} for player in players], safe=False)


def update_display_name(request):
    """Update the user's display name."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        new_name = data.get("display_name", "").strip()

        # Validate the name
        if not new_name:
            return JsonResponse({"error": "Name cannot be empty"}, status=400)

        if len(new_name) < 6:
            return JsonResponse({"error": "Name must be at least 6 characters long"}, status=400)

        if len(new_name) > 14:
            return JsonResponse({"error": "Name must be 14 characters or less"}, status=400)

        if not re.match(r"^[a-zA-Z0-9\s]+$", new_name):
            return JsonResponse({"error": "Name can only contain letters, numbers and spaces"}, status=400)

        # Update the user's display name
        user_data = UserData.get_or_create_user(request.session.session_key)
        user_data.display_name = new_name
        user_data.save()

        return JsonResponse({"success": True})
    except Exception as e:
        logger.error(f"Error updating display name: {e}")
        return JsonResponse({"error": "Server error"}, status=500)


def generate_random_name(request):
    """Generate a random display name for the user."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Try up to 5 times to generate a valid name
        max_attempts = 5
        for attempt in range(max_attempts):
            # Use current timestamp as part of the seed to ensure different names each time
            seed = f"{request.session.session_key}_{datetime.now().timestamp()}_{attempt}"
            random_name = Player.generate_random_name(seed)

            # Validate the generated name
            if len(random_name) >= 6 and len(random_name) <= 14 and re.match(r"^[a-zA-Z0-9\s]+$", random_name):
                return JsonResponse({"name": random_name})

            # If we're on the last attempt and still haven't found a valid name,
            # return a simple fallback name
            if attempt == max_attempts - 1:
                return JsonResponse({"name": "Player" + str(random.randint(1000, 9999))})

        return JsonResponse({"error": "Failed to generate valid name"}, status=500)
    except Exception as e:
        logger.error(f"Error generating random name: {e}")
        return JsonResponse({"error": "Server error"}, status=500)


@basic_auth_required
def metrics_view(request):
    """Custom metrics view that adds application-specific metrics."""
    timer_stop = track_request_latency("metrics")
    try:
        # Update metrics based on current DB state
        # Count active games based on DB state (not perfect but gives an estimate)
        active_games_count = GameCompletion.objects.filter(completed_at__gte=datetime.now() - timedelta(hours=1)).count()
        update_active_games(active_games_count)

        # Update total guesses gauge for today
        today = datetime.now().date()
        today_str = today.isoformat()
        total_guesses = GameResult.get_total_guesses(today)
        update_total_guesses_gauge(today_str, total_guesses)

        # Update PythonAnywhere CPU metrics if environment variables are set
        pa_username = settings.PYTHONANYWHERE_USERNAME
        pa_token = settings.PYTHONANYWHERE_API_TOKEN
        pa_host = settings.PYTHONANYWHERE_HOST

        if pa_username and pa_token:
            try:
                update_pythonanywhere_cpu_metrics(pa_username, pa_token, pa_host)
            except Exception as e:
                logger.error(f"Error updating PythonAnywhere CPU metrics: {e}")

        # Return all metrics
        return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
    finally:
        timer_stop()
