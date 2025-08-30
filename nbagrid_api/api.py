from datetime import datetime, timedelta
from typing import Optional

from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader
from django.http import JsonResponse

from django.conf import settings

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.metrics import track_request_latency
from nbagrid_api_app.models import GameFilterDB, ImpressumContent, LastUpdated, Player, Team

api = NinjaAPI()
game_cache = {}
solutions_cache = {}


class GameDateTooEarlyException(Exception):
    pass


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        if key == settings.NBAGRID_API_KEY:
            return key
        return None


header_key = ApiKey()


def is_valid_date(given_date: datetime) -> bool:
    earliest_date = datetime(year=2025, month=4, day=1)
    if given_date < earliest_date:
        return False
    if given_date > datetime.now():
        return False
    return True

def has_cached_game(given_date: datetime):
    # check whether the given_date already has a cached game by checking the GameFilterDB table
    return GameFilterDB.objects.filter(date=given_date).exists()

def get_first_available_date():
    # get the first available date before April 1st where there is NO cached game
    # get the earliest date in the GameFilterDB table
    start_date = GameFilterDB.objects.order_by('date').first().date
    # check whether the date before start_date has a cached game
    target_date = start_date - timedelta(days=1)
    while has_cached_game(target_date):
        target_date = target_date - timedelta(days=1)
    return target_date    

def get_cached_game_for_date(given_date: datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if given_date not in game_cache:
        builder = GameBuilder(given_date.timestamp())
        (filter_static, filter_dynamic) = builder.get_tuned_filters(given_date)
        game_cache[given_date] = (filter_static, filter_dynamic)
    return game_cache[given_date]


def get_cached_solutions_for_date(given_date: datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if given_date not in solutions_cache:
        game_cache_filters = get_cached_game_for_date(given_date)
        filter_static, filter_dynamic = game_cache_filters
        result_players = Player.objects.all()
        both_filters = []
        both_filters.extend(filter_static)
        both_filters.extend(filter_dynamic)
        for f in both_filters:
            result_players = f.apply_filter(result_players)
        solutions_cache[given_date] = result_players
    return solutions_cache[given_date]


class PlayerSchema(Schema):
    name: str = "Player"
    last_name: str = ""
    display_name: str = "Player"
    draft_year: int = 0
    draft_round: int = 0
    draft_number: int = 0
    is_undrafted: bool = False
    is_greatest_75: bool = False
    num_seasons: int = 0
    weight_kg: int = 0
    height_cm: int = 0
    country: str = ""
    position: str = ""
    base_salary: int = 0  # Base salary in USD
    career_gp: int = 0
    career_gs: int = 0
    career_min: int = 0
    career_high_ast: int = 0
    career_high_reb: int = 0
    career_high_stl: int = 0
    career_high_blk: int = 0
    career_high_to: int = 0
    career_high_pts: int = 0
    career_high_fg: int = 0
    career_high_3p: int = 0
    career_high_ft: int = 0
    career_apg: float = 0.0
    career_ppg: float = 0.0
    career_rpg: float = 0.0
    career_bpg: float = 0.0
    career_spg: float = 0.0
    career_tpg: float = 0.0
    career_fgp: float = 0.0
    career_3gp: float = 0.0
    career_ftp: float = 0.0
    career_fga: float = 0.0
    career_3pa: float = 0.0
    career_fta: float = 0.0
    is_award_mip: bool = False
    is_award_champ: bool = False
    is_award_dpoy: bool = False
    is_award_all_nba_first: bool = False
    is_award_all_nba_second: bool = False
    is_award_all_nba_third: bool = False
    is_award_all_rookie: bool = False
    is_award_all_defensive: bool = False
    is_award_all_star: bool = False
    is_award_all_star_mvp: bool = False
    is_award_rookie_of_the_year: bool = False
    is_award_mvp: bool = False
    is_award_finals_mvp: bool = False
    is_award_olympic_gold_medal: bool = False
    is_award_olympic_silver_medal: bool = False
    is_award_olympic_bronze_medal: bool = False
    teammates: Optional[list[int]] = None  # List of player stats_ids who are teammates


class TeamSchema(Schema):
    name: str
    abbr: str


@api.post("/team/{stats_id}", auth=header_key)
def update_team(request, stats_id: int, data: TeamSchema):
    timer_stop = track_request_latency("update_team")
    try:
        try:
            # Try to get existing team or create a new one
            team, created = Team.objects.get_or_create(stats_id=stats_id, defaults={"name": data.name, "abbr": data.abbr})

            # Update all fields from the schema
            for field in data.dict():
                setattr(team, field, getattr(data, field))

            team.save()

            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="team_data",
                updated_by=f"API update for team {stats_id}",
                notes=f"{'Created' if created else 'Updated'} team {team.name}",
            )

            action = "created" if created else "updated"
            return {"status": "success", "message": f"Team {team.name} {action} successfully"}

        except Exception as e:
            timer_stop(status="error")
            return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()


class LastUpdatedSchema(Schema):
    data_type: str
    updated_by: str
    notes: Optional[str] = None

# Schema for submitting a prebuilt game
class PrebuiltGameSchema(Schema):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    filters: dict  # Dictionary with 'row' and 'col' keys containing filter configurations
    game_title: Optional[str] = None  # Optional title for the pre-generated grid
    force: bool = False  # Allow overwriting future grids (never past grids)


@api.post("/player/{stats_id}", auth=header_key)
def update_player(request, stats_id: int, data: PlayerSchema):
    timer_stop = track_request_latency("update_player")
    try:
        try:
            # Try to get existing player or create a new one
            player, created = Player.objects.get_or_create(
                stats_id=stats_id, defaults={"name": data.name or f"Player {stats_id}"}  # Use provided name or generate one
            )

            # Handle teammates separately since it's a ManyToManyField
            data_dict = data.dict()
            teammates_data = data_dict.pop('teammates', None)
            
            # Update all fields from the schema (excluding teammates)
            for field in data_dict:
                if field != "name" or not created:  # Don't update name if we just created the player
                    setattr(player, field, getattr(data, field))

            player.save()

            # Handle teammates if provided
            if teammates_data is not None:
                # Clear existing teammates
                player.teammates.clear()
                
                # Add new teammates
                if teammates_data:
                    try:
                        # Get all teammate players by stats_id
                        teammate_players = Player.objects.filter(stats_id__in=teammates_data)
                        
                        # Add them to the player's teammates
                        player.teammates.add(*teammate_players)
                        
                        # Also add the reverse relationship (bidirectional)
                        for teammate in teammate_players:
                            if player not in teammate.teammates.all():
                                teammate.teammates.add(player)
                        
                    except Player.DoesNotExist as e:
                        return JsonResponse({"status": "error", "message": f"One or more teammate players not found: {str(e)}"}, status=404)

            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="player_data",
                updated_by=f"API update for player {stats_id}",
                notes=f"{'Created' if created else 'Updated'} player {player.name}" + (f" with {len(teammates_data) if teammates_data else 0} teammates" if teammates_data is not None else ""),
            )

            action = "created" if created else "updated"
            teammate_info = f" with {len(teammates_data) if teammates_data else 0} teammates" if teammates_data is not None else ""
            return {"status": "success", "message": f"Player {player.name} {action} successfully{teammate_info}"}

        except Exception as e:
            timer_stop(status="error")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    finally:
        timer_stop()


@api.get("/updates")
def get_all_updates(request):
    """Get all update timestamps by data type"""
    timer_stop = track_request_latency("get_all_updates")
    try:
        updates = LastUpdated.objects.all()
        return [
            {
                "data_type": update.data_type,
                "last_updated": update.last_updated.isoformat() if update.last_updated else None,
                "updated_by": update.updated_by,
                "notes": update.notes,
            }
            for update in updates
        ]
    finally:
        timer_stop()


@api.get("/updates/{data_type}")
def get_update_timestamp(request, data_type: str):
    """Get the most recent update timestamp for a specific data type"""
    timer_stop = track_request_latency("get_update_timestamp")
    try:
        update = LastUpdated.objects.get(data_type=data_type)
        return {
            "data_type": update.data_type,
            "last_updated": update.last_updated.isoformat() if update.last_updated else None,
            "updated_by": update.updated_by,
            "notes": update.notes,
        }
    except LastUpdated.DoesNotExist:
        return JsonResponse({"error": f"No update record found for '{data_type}'"}, status=404)
    finally:
        timer_stop()


@api.post("/updates", auth=header_key)
def record_update(request, data: LastUpdatedSchema):
    """Record a new update timestamp"""
    timer_stop = track_request_latency("record_update")
    try:
        update = LastUpdated.update_timestamp(data_type=data.data_type, updated_by=data.updated_by, notes=data.notes)
        return {
            "status": "success",
            "data_type": update.data_type,
            "last_updated": update.last_updated.isoformat(),
            "updated_by": update.updated_by,
            "notes": update.notes,
        }
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    finally:
        timer_stop()


@api.post("/upload_prebuilt_game", auth=header_key)
def upload_prebuilt_game(request, data: PrebuiltGameSchema):
    """Upload a pre-generated grid to the database"""
    timer_stop = track_request_latency("upload_prebuilt_game")
    try:
        try:
            # Parse the date from the schema
            if data.year and data.month and data.day:
                target_date = datetime(year=data.year, month=data.month, day=data.day).date()
            else:
                # If no date is given add them to the first available date before April 1st 2025
                target_date = get_first_available_date()
            
            # Check if grid already exists for this date
            from nbagrid_api_app.models import GameFilterDB
            existing_grid = GameFilterDB.objects.filter(date=target_date).exists()
            
            if existing_grid:
                # Never allow overwriting past grids
                if target_date < datetime.now().date():
                    return {"status": "error", "message": f"Cannot overwrite past grid for {target_date}"}, 400
                
                # For future grids, only allow overwriting if force=True
                if not data.force:
                    return {"status": "error", "message": f"Grid already exists for {target_date}. Use force=True to overwrite."}, 400
                
                # If force=True and it's a future grid, delete existing grid first
                if data.force and target_date > datetime.now().date():
                    # Delete existing filters and metadata
                    GameFilterDB.objects.filter(date=target_date).delete()
                    from nbagrid_api_app.models import GridMetadata, GameGrid
                    GridMetadata.objects.filter(date=target_date).delete()
                    GameGrid.objects.filter(date=target_date).delete()
            
            # Validate filter configuration
            filters = data.filters
            if not filters or not isinstance(filters, dict):
                return {"status": "error", "message": "Invalid filters format"}, 400
            
            row_filters = filters.get("row", {})
            col_filters = filters.get("col", {})
            
            # Validate we have the correct number of filters
            if len(row_filters) != 3 or len(col_filters) != 3:
                return {"status": "error", "message": f"Invalid filter configuration: expected 3 row and 3 column filters, got {len(row_filters)} row and {len(col_filters)} column"}, 400
            
            # Import necessary modules
            from nbagrid_api_app.models import GameFilterDB, GridMetadata, LastUpdated, GameGrid
            from nbagrid_api_app.GameBuilder import GameBuilder
            
            # Create GameFilterDB objects for each filter
            # Process row filters (static filters)
            for index, filter_data in row_filters.items():
                GameFilterDB.objects.create(
                    date=target_date,
                    filter_type="static",
                    filter_class=filter_data["class"],
                    filter_config=filter_data["config"],
                    filter_index=int(index),
                )
            
            # Process column filters (dynamic filters)
            for index, filter_data in col_filters.items():
                GameFilterDB.objects.create(
                    date=target_date,
                    filter_type="dynamic",
                    filter_class=filter_data["class"],
                    filter_config=filter_data["config"],
                    filter_index=int(index),
                )
            
            # Create the GameGrid object using GameBuilder
            builder = GameBuilder()
            builder.get_tuned_filters(target_date)
            
            # Create GridMetadata
            if data.game_title:
                GridMetadata.objects.create(
                    date=target_date,
                    game_title=data.game_title
                )
            
            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="game_data",
                updated_by="API prebuilt game upload",
                notes=f"Uploaded pre-generated game for {target_date}" + (" (overwritten)" if existing_grid and data.force else ""),
            )
            
            action = "overwritten" if existing_grid and data.force else "uploaded"
            return {
                "status": "success",
                "message": f"Pre-generated game {action} successfully for {target_date}",
                "date": {
                    "year": target_date.year,
                    "month": target_date.month,
                    "day": target_date.day
                },
                "action": action,
                "was_overwritten": existing_grid and data.force
            }
            
        except Exception as e:
            timer_stop(status="error")
            return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()


@api.post("/player/{stats_id}/team/{team_stats_id}", auth=header_key)
def add_player_team_relationship(request, stats_id: int, team_stats_id: int):
    """Add a player-team relationship."""
    timer_stop = track_request_latency("add_player_team_relationship")
    try:
        try:
            # Get the player and team
            player = Player.objects.get(stats_id=stats_id)
            team = Team.objects.get(stats_id=team_stats_id)

            # Add the relationship
            player.teams.add(team)

            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="player_team_relationship",
                updated_by=f"API update for player {stats_id} and team {team_stats_id}",
                notes=f"Added relationship between {player.name} and {team.name}",
            )

            return {"status": "success", "message": f"Added relationship between {player.name} and {team.name}"}

        except Player.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Player with stats_id {stats_id} not found"}, status=404)
        except Team.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Team with stats_id {team_stats_id} not found"}, status=404)
        except Exception as e:
            timer_stop(status="error")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    finally:
        timer_stop()


class TeammateSchema(Schema):
    teammate_stats_ids: list[int]  # List of player stats_ids to add as teammates


@api.post("/player/{stats_id}/teammates", auth=header_key)
def update_player_teammates(request, stats_id: int, data: TeammateSchema):
    """Update a player's teammates."""
    timer_stop = track_request_latency("update_player_teammates")
    try:
        try:
            # Get the player
            player = Player.objects.get(stats_id=stats_id)

            # Clear existing teammates
            player.teammates.clear()
            
            # Add new teammates
            if data.teammate_stats_ids:
                try:
                    # Get all teammate players by stats_id
                    teammate_players = Player.objects.filter(stats_id__in=data.teammate_stats_ids)
                    
                    # Add them to the player's teammates
                    player.teammates.add(*teammate_players)
                    
                    # Also add the reverse relationship (bidirectional)
                    for teammate in teammate_players:
                        if player not in teammate.teammates.all():
                            teammate.teammates.add(player)
                    
                except Player.DoesNotExist as e:
                    return JsonResponse({"status": "error", "message": f"One or more teammate players not found: {str(e)}"}, status=404)

            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="player_teammate_relationship",
                updated_by=f"API update for player {stats_id} teammates",
                notes=f"Updated teammates for {player.name} with {len(data.teammate_stats_ids)} teammates",
            )

            return {"status": "success", "message": f"Updated teammates for {player.name} with {len(data.teammate_stats_ids)} teammates"}

        except Player.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Player with stats_id {stats_id} not found"}, status=404)
        except Exception as e:
            timer_stop(status="error")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    finally:
        timer_stop()


@api.get("/player/{stats_id}/teammates")
def get_player_teammates(request, stats_id: int):
    """Get a player's teammates."""
    timer_stop = track_request_latency("get_player_teammates")
    try:
        try:
            # Get the player
            player = Player.objects.get(stats_id=stats_id)
            
            # Get teammates
            teammates = player.teammates.all()
            
            return {
                "player_name": player.name,
                "player_stats_id": stats_id,
                "teammates": [
                    {
                        "name": teammate.name,
                        "stats_id": teammate.stats_id,
                        "position": teammate.position,
                        "team_abbrs": [team.abbr for team in teammate.teams.all()]
                    }
                    for teammate in teammates
                ],
                "teammate_count": len(teammates)
            }

        except Player.DoesNotExist:
            return JsonResponse({"status": "error", "message": f"Player with stats_id {stats_id} not found"}, status=404)
        except Exception as e:
            timer_stop(status="error")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    finally:
        timer_stop()


@api.get("/health")
def health_check(request):
    """Health check endpoint that returns 200 if the service is up and running"""
    return {"status": "healthy", "message": "Service is up and running"}


class ImpressumContentSchema(Schema):
    title: str
    content: str
    order: int


@api.get("/impressum", response=list[ImpressumContentSchema])
def get_impressum_content(request):
    """Get active impressum content ordered by order field"""
    content_items = ImpressumContent.objects.filter(is_active=True).order_by('order', 'created_at')
    return [
        {
            "title": item.title,
            "content": item.content,
            "order": item.order,
        }
        for item in content_items
    ]


@api.get("/game/{year}/{month}/{day}/cell/{row}/{col}/players")
def get_cell_correct_players(request, year: int, month: int, day: int, row: int, col: int):
    """Get correct players for a specific cell in a finished game."""
    timer_stop = track_request_latency("get_cell_correct_players")
    try:
        from datetime import date, timedelta
        from django.core.cache import cache
        from nbagrid_api_app.GameBuilder import GameBuilder
        
        # Rate limiting: Allow max 10 requests per minute per IP
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        cache_key = f"cell_players_rate_limit_{client_ip}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= 10:
            return JsonResponse({"error": "Rate limit exceeded. Please try again later."}, status=429)
        
        # Increment rate limit counter (expires in 60 seconds)
        cache.set(cache_key, request_count + 1, 60)
        
        # Validate date range - only allow dates from the last 2 years to prevent abuse
        try:
            requested_date = date(year, month, day)
        except ValueError:
            return JsonResponse({"error": "Invalid date"}, status=400)
        
        # Restrict to reasonable date range
        today = date.today()
        two_years_ago = today - timedelta(days=730)
        if requested_date < two_years_ago or requested_date > today:
            return JsonResponse({"error": "Date out of range"}, status=400)
        
        # Only allow access to finished games (past dates)
        if requested_date >= today:
            return JsonResponse({"error": "Game is not finished yet"}, status=400)
        
        # Check if the game exists
        from nbagrid_api_app.models import GameFilterDB
        if not GameFilterDB.objects.filter(date=requested_date).exists():
            return JsonResponse({"error": "Game not found for this date"}, status=404)
        
        # Validate cell coordinates (standard 3x3 grid)
        if row < 0 or row >= 3 or col < 0 or col >= 3:
            return JsonResponse({"error": "Invalid cell coordinates"}, status=400)
        
        # Build the game grid using the same approach as the main views
        from nbagrid_api_app.views import get_game_filters, build_grid
        
        # Convert date to datetime for get_game_filters
        from datetime import datetime
        requested_datetime = datetime.combine(requested_date, datetime.min.time())
        
        # Get the filters for this date
        static_filters, dynamic_filters = get_game_filters(requested_datetime)
        
        # Build the grid
        game_grid = build_grid(static_filters, dynamic_filters)
        
        if not game_grid:
            return JsonResponse({"error": "Failed to build game grid"}, status=500)
        
        # Get correct players for the specific cell
        cell_key = f"{row}_{col}"
        cell = game_grid[row][col]
        
        # Initialize the list for this cell
        correct_players = []
        
        # Add correct players (no wrong guesses for API since we don't have game state)
        matching_players = Player.objects.all()
        for f in cell["filters"]:
            matching_players = f.apply_filter(matching_players)
        
        # Limit results to prevent huge responses (max 50 players per cell)
        matching_players = matching_players[:50]
        
        # Include player stats for each matching player
        for p in matching_players:
            correct_players.append({
                "name": p.name, 
                "stats": [f.get_player_stats_str(p) for f in cell["filters"]], 
                "is_wrong_guess": False,
                "player_id": p.stats_id
            })
        
        return {
            "cell_key": cell_key,
            "row": row,
            "col": col,
            "players": correct_players,
            "player_count": len(correct_players)
        }
        
    except Exception as e:
        timer_stop(status="error")
        return JsonResponse({"error": "Internal server error"}, status=500)
    finally:
        timer_stop()
