from datetime import datetime
from typing import Optional

from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader

from django.conf import settings

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.metrics import track_request_latency
from nbagrid_api_app.models import ImpressumContent, LastUpdated, Player, Team

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
    filters: dict  # Dictionary with 'row' and 'col' keys containing filter configurations


@api.post("/player/{stats_id}", auth=header_key)
def update_player(request, stats_id: int, data: PlayerSchema):
    timer_stop = track_request_latency("update_player")
    try:
        try:
            # Try to get existing player or create a new one
            player, created = Player.objects.get_or_create(
                stats_id=stats_id, defaults={"name": data.name or f"Player {stats_id}"}  # Use provided name or generate one
            )

            # Update all fields from the schema
            for field in data.dict():
                if field != "name" or not created:  # Don't update name if we just created the player
                    setattr(player, field, getattr(data, field))

            player.save()

            # Record the update timestamp
            LastUpdated.update_timestamp(
                data_type="player_data",
                updated_by=f"API update for player {stats_id}",
                notes=f"{'Created' if created else 'Updated'} player {player.name}",
            )

            action = "created" if created else "updated"
            return {"status": "success", "message": f"Player {player.name} {action} successfully"}

        except Exception as e:
            timer_stop(status="error")
            return {"status": "error", "message": str(e)}, 500
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
        return {"error": f"No update record found for '{data_type}'"}, 404
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
            return {"status": "error", "message": f"Player with stats_id {stats_id} not found"}, 404
        except Team.DoesNotExist:
            return {"status": "error", "message": f"Team with stats_id {team_stats_id} not found"}, 404
        except Exception as e:
            timer_stop(status="error")
            return {"status": "error", "message": str(e)}, 500
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
