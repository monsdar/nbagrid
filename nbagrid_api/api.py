from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader
from nbagrid_api_app.models import Player, LastUpdated, GameFilterDB
from nbagrid_api_app.GameBuilder import GameBuilder
from django.conf import settings
from nbagrid_api_app.metrics import track_request_latency, api_request_counter

from datetime import datetime, timedelta
from typing import Optional

api = NinjaAPI()
game_cache = {}
solutions_cache = {}

class GameDateTooEarlyException(Exception): pass

class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"
    def authenticate(self, request, key):
        if key == settings.NBAGRID_API_KEY:
            return key
        return None

header_key = ApiKey()

def is_valid_date(given_date:datetime) -> bool:
    earliest_date = datetime(year=2025, month=4, day=1)
    if given_date < earliest_date:
        return False
    if given_date > datetime.now():
        return False
    return True

def is_valid_future_date(given_date:datetime) -> bool:
    """Validate if a date is valid for generating a future game."""
    earliest_date = datetime(year=2025, month=4, day=1)
    
    # Date must be at least earliest_date
    if given_date < earliest_date:
        return False
        
    # For future games, we allow dates after now
    return True

def get_cached_game_for_date(given_date:datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if not given_date in game_cache:
        builder = GameBuilder(given_date.timestamp())
        (filter_static, filter_dynamic) = builder.get_tuned_filters(given_date)
        game_cache[given_date] = (filter_static, filter_dynamic)
    return game_cache[given_date]

def get_cached_solutions_for_date(given_date:datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if not given_date in solutions_cache:
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

@api.get("/players/{name}")
def get_players_by_searchstr(request, name: str, num_players: int=5):
    timer_stop = track_request_latency('get_players_by_name')
    try:
        if len(name) < 3:
            return []
        return [{"stats_id": player.stats_id, "name": player.name} for player in Player.objects.filter(name__contains=name)[:num_players]]
    finally:
        timer_stop()

class PlayerSchema(Schema):
    name: str = "Player"
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
    
class LastUpdatedSchema(Schema):
    data_type: str
    updated_by: str
    notes: Optional[str] = None

# Schema for the game grid generation API
class GameGridSchema(Schema):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None

# Schema for submitting a prebuilt GameFilter
class GameFilterSchema(Schema):
    filter_type: str  # 'static' or 'dynamic'
    filter_class: str  # e.g., 'PositionFilter', 'DynamicGameFilter'
    filter_config: dict  # Configuration for the filter
    filter_index: int  # Position in the grid

# Schema for submitting a prebuilt game
class PrebuiltGameSchema(Schema):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    filters: list[GameFilterSchema]  # List of filter configurations
    
@api.post("/player/{stats_id}", auth=header_key)
def update_player(request, stats_id: int, data: PlayerSchema):
    timer_stop = track_request_latency('update_player')
    try:
        try:
            # Try to get existing player or create a new one
            player, created = Player.objects.get_or_create(
                stats_id=stats_id,
                defaults={'name': data.name or f"Player {stats_id}"}  # Use provided name or generate one
            )
            
            # Update all fields from the schema
            for field in data.dict():
                if field != 'name' or not created:  # Don't update name if we just created the player
                    setattr(player, field, getattr(data, field))
            
            player.save()
            
            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="player_data",
                updated_by=f"API update for player {stats_id}",
                notes=f"{'Created' if created else 'Updated'} player {player.name}"
            )
            
            action = "created" if created else "updated"
            return {"status": "success", "message": f"Player {player.name} {action} successfully"}
                
        except Exception as e:
            timer_stop(status='error')
            return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()


def get_next_available_date():            # Find the next available date that doesn't have a game
    target_date = datetime.now().date() + timedelta(days=1)
    while GameFilterDB.objects.filter(date=target_date).exists():
        target_date += timedelta(days=1)
    target_date = datetime.combine(target_date, datetime.min.time())
    return target_date

@api.put("/game", auth=header_key)
def submit_prebuilt_game(request, data: PrebuiltGameSchema):
    """Submit a prebuilt game with custom filters"""
    timer_stop = track_request_latency('submit_prebuilt_game')
    try:
        # Determine the target date
        if data.year and data.month and data.day:
            # If a specific date is provided
            target_date = datetime(year=data.year, month=data.month, day=data.day)
            
            # Validate the date is suitable for future game generation
            if not is_valid_future_date(target_date):
                return {"status": "error", "message": "Invalid date - must be on or after April 1, 2025"}, 400
            
            # Check if the date is in the past
            if target_date.date() <= datetime.now().date():
                return {"status": "error", "message": "Cannot generate games for dates in the past"}, 400
                
            # Check if a game already exists for this date
            if GameFilterDB.objects.filter(date=target_date.date()).exists():
                return {"status": "error", "message": f"A game already exists for date {target_date.date()}"}, 409
        else: # Find the next available date that doesn't have a game
            target_date = get_next_available_date()
        
        # Validate filter configuration
        if not data.filters or len(data.filters) == 0:
            return {"status": "error", "message": "No filters provided"}, 400
            
        # Count static and dynamic filters
        static_filters = [f for f in data.filters if f.filter_type == 'static']
        dynamic_filters = [f for f in data.filters if f.filter_type == 'dynamic']
        
        # For a standard 3x3 grid, we expect 3 static and 3 dynamic filters
        if len(static_filters) != 3 or len(dynamic_filters) != 3:
            return {
                "status": "error", 
                "message": f"Invalid filter configuration: expected 3 static and 3 dynamic filters, got {len(static_filters)} static and {len(dynamic_filters)} dynamic"
            }, 400
        
        # Create GameFilterDB objects for each filter
        for filter_config in data.filters:
            GameFilterDB.objects.create(
                date=target_date.date(),
                filter_type=filter_config.filter_type,
                filter_class=filter_config.filter_class,
                filter_config=filter_config.filter_config,
                filter_index=filter_config.filter_index
            )
        
        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="game_generation",
            updated_by="API prebuilt game submission",
            notes=f"Prebuilt game submitted for {target_date.date()}"
        )
        
        # Return success with the date
        return {
            "status": "success", 
            "message": f"Prebuilt game successfully added for {target_date.date()}",
            "date": {
                "year": target_date.year,
                "month": target_date.month,
                "day": target_date.day
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()

@api.put("/game/generate", auth=header_key)
def generate_game(request, data: GameGridSchema = None):
    """Generate a new game for the specified date or the next available date"""
    timer_stop = track_request_latency('generate_game')
    try:
        # Determine the target date
        if data and data.year and data.month and data.day:
            # If a specific date is provided
            target_date = datetime(year=data.year, month=data.month, day=data.day)
            
            # Validate the date is suitable for future game generation
            if not is_valid_future_date(target_date):
                return {"status": "error", "message": "Invalid date - must be on or after April 1, 2025"}, 400
            
            # Check if the date is in the past
            if target_date.date() <= datetime.now().date():
                return {"status": "error", "message": "Cannot generate games for dates in the past"}, 400
                
            # Check if a game already exists for this date
            if GameFilterDB.objects.filter(date=target_date.date()).exists():
                return {"status": "error", "message": f"A game already exists for date {target_date.date()}"}, 409
        else: # Find the next available date that doesn't have a game
            target_date = get_next_available_date()
        
        # Generate the game filters
        builder = GameBuilder(target_date.timestamp())
        static_filters, dynamic_filters = builder.get_tuned_filters(target_date)
        
        # Record the update timestamp
        LastUpdated.update_timestamp(
            data_type="game_generation",
            updated_by="API game generation",
            notes=f"Game generated for {target_date.date()}"
        )
        
        # Return success with the date
        return {
            "status": "success", 
            "message": f"Game grid generated for {target_date.date()}",
            "date": {
                "year": target_date.year,
                "month": target_date.month,
                "day": target_date.day
            },
            "filters": {
                "static": [f.get_desc() for f in static_filters],
                "dynamic": [f.get_desc() for f in dynamic_filters]
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()

@api.get("/updates")
def get_all_updates(request):
    """Get all update timestamps by data type"""
    timer_stop = track_request_latency('get_all_updates')
    try:
        updates = LastUpdated.objects.all()
        return [
            {
                "data_type": update.data_type,
                "last_updated": update.last_updated.isoformat() if update.last_updated else None,
                "updated_by": update.updated_by,
                "notes": update.notes
            }
            for update in updates
        ]
    finally:
        timer_stop()

@api.get("/updates/{data_type}")
def get_update_timestamp(request, data_type: str):
    """Get the most recent update timestamp for a specific data type"""
    timer_stop = track_request_latency('get_update_timestamp')
    try:
        update = LastUpdated.objects.get(data_type=data_type)
        return {
            "data_type": update.data_type,
            "last_updated": update.last_updated.isoformat() if update.last_updated else None,
            "updated_by": update.updated_by,
            "notes": update.notes
        }
    except LastUpdated.DoesNotExist:
        return {"error": f"No update record found for '{data_type}'"}, 404
    finally:
        timer_stop()

@api.post("/updates", auth=header_key)
def record_update(request, data: LastUpdatedSchema):
    """Record a new update timestamp"""
    timer_stop = track_request_latency('record_update')
    try:
        update = LastUpdated.update_timestamp(
            data_type=data.data_type,
            updated_by=data.updated_by,
            notes=data.notes
        )
        return {
            "status": "success",
            "data_type": update.data_type,
            "last_updated": update.last_updated.isoformat(),
            "updated_by": update.updated_by,
            "notes": update.notes
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
    finally:
        timer_stop()
    