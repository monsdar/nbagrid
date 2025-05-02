from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader
from nbagrid_api_app.models import Player, LastUpdated, GameFilterDB
from nbagrid_api_app.GameBuilder import GameBuilder
from django.conf import settings

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
    if len(name) < 3:
        return []
    return [{"stats_id": player.stats_id, "name": player.name} for player in Player.objects.filter(name__contains=name)[:num_players]]

@api.get("/game/{year}/{month}/{day}")
def get_game_for_date(request, year: int, month: int, day: int):
    given_date = datetime(year=year, month=month, day=day)
    (filter_static, filter_dynamic) = get_cached_game_for_date(given_date)
    result_players = get_cached_solutions_for_date(given_date)
    return {
        "static_filter": filter_static.get_desc(),
        "dynamic_filter": filter_dynamic.get_desc(),
        "static_filter_detailed": filter_static.get_detailed_desc(),
        "dynamic_filter_detailed": filter_dynamic.get_detailed_desc(),
        "num_solutions": len(result_players)
        }

@api.post("/game/{year}/{month}/{day}/{player_id}")
def post_player_for_date(request, year: int, month: int, day: int, player_id: int):
    try:
        given_date = datetime(year=year, month=month, day=day)
        result_players = get_cached_solutions_for_date(given_date)
        result_players.get(stats_id=player_id)
        return 200
    except GameDateTooEarlyException:
        return 400
    except Player.DoesNotExist:
        return 404

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
    
@api.post("/player/{stats_id}", auth=header_key)
def update_player(request, stats_id: int, data: PlayerSchema):
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
        return {"status": "error", "message": str(e)}, 500

@api.put("/game/generate", auth=header_key)
def generate_game(request, data: GameGridSchema = None):
    """Generate a game grid for a future date"""
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
        else:
            # Find the next available date that doesn't have a game
            target_date = datetime.now().date() + timedelta(days=1)
            while GameFilterDB.objects.filter(date=target_date).exists():
                target_date += timedelta(days=1)
            target_date = datetime.combine(target_date, datetime.min.time())
        
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

@api.get("/updates")
def get_all_updates(request):
    """Get all update timestamps"""
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

@api.get("/updates/{data_type}")
def get_update_timestamp(request, data_type: str):
    """Get the last update timestamp for a specific data type"""
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

@api.post("/updates", auth=header_key)
def record_update(request, data: LastUpdatedSchema):
    """Record a new update timestamp"""
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
    