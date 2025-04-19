
from ninja import NinjaAPI
from nbagrid_api_app.models import Player
from nbagrid_api_app.GameBuilder import GameBuilder

from datetime import datetime

api = NinjaAPI()
game_cache = {}
solutions_cache = {}

class GameDateTooEarlyException(Exception): pass

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
    