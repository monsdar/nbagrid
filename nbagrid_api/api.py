from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader
from nbagrid_api_app.models import Player
from nbagrid_api_app.GameBuilder import GameBuilder
from django.conf import settings

from datetime import datetime

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

def get_cached_game_for_date(given_date:datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if not given_date in game_cache:
        builder = GameBuilder(given_date.timestamp())
        (filter_static, filter_dynamic) = builder.get_tuned_filter_pair()
        game_cache[given_date] = (filter_static, filter_dynamic)
    return game_cache[given_date]

def get_cached_solutions_for_date(given_date:datetime):
    if not is_valid_date(given_date):
        raise GameDateTooEarlyException
    if not given_date in solutions_cache:
        (filter_static, filter_dynamic) = get_cached_game_for_date(given_date)
        solutions_cache[given_date] = filter_static.apply_filter(filter_dynamic.apply_filter(Player.objects.all()))
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
        action = "created" if created else "updated"
        return {"status": "success", "message": f"Player {player.name} {action} successfully"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
    