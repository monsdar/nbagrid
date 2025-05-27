from abc import abstractmethod
from django.db.models import Manager, Count, Subquery, OuterRef
from nbagrid_api_app.models import Player, Team
import random
import logging

logger = logging.getLogger(__name__)

class GameFilter(object):
    @abstractmethod
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        pass
    @abstractmethod
    def get_desc(self) -> str:
        pass
    @abstractmethod
    def get_player_stats_str(self, player: Player) -> str:
        pass
    @abstractmethod
    def get_detailed_desc(self) -> str:
        pass

    def __str__(self) -> str:
        return self.get_desc()

class DynamicGameFilter(GameFilter):
    def __init__(self, config):
        self.config = config
        self.current_value = self._get_initial_value()
        
    def _get_initial_value(self):
        if 'initial_value_step' in self.config:
            return random.choice(range(self.config['initial_min_value'], self.config['initial_max_value'], self.config['initial_value_step']))
        if 'initial_min_value' in self.config and 'initial_max_value' in self.config:
            return random.randint(self.config['initial_min_value'], self.config['initial_max_value'])
        return 0
    
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        field = self.config['field']
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            comparison_operator = '__lte'
        else:   
            comparison_operator = '__gte'
        return players.filter(**{f"{field}{comparison_operator}": self.current_value})
    
    def get_player_stats_str(self, player: Player) -> str:
        description = self.config['stats_desc'] if 'stats_desc' in self.config else self.config['description']
        field = self.config['field']
        stat_value = getattr(player, field)
        if stat_value > 1000000:
            stat_value = f"{stat_value / 1000000:.1f}"
        unit = f" {self.config['unit']}" if 'unit' in self.config else ''
        return f"{description} {stat_value}{unit}"
    
    def get_desc(self) -> str:
        description = self.config['description']
        unit = f" {self.config['unit']}" if 'unit' in self.config else ''
        desc_operator = '+'
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            desc_operator = '-'
        display_value = self.current_value
        if self.current_value > 1000000:
            display_value = f"{self.current_value / 1000000:.1f}"
        return f"{description} {display_value}{desc_operator}{unit}"
    
    def get_detailed_desc(self) -> str:
        return self.config.get('detailed_desc', f'{self.get_desc()}')
                
    def widen_filter(self):
        widen_step = -(self.config['widen_step'] if 'widen_step' in self.config else 1)
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            widen_step = -widen_step
        self.current_value += widen_step
        
        # Make sure the game stays interesting by not going out of a certain range
        if 'initial_min_value' in self.config and self.current_value < self.config['initial_min_value']:
            self.current_value = self.config['initial_min_value']
        if 'initial_max_value' in self.config and self.current_value > self.config['initial_max_value']:
            self.current_value = self.config['initial_max_value']
                    
    def narrow_filter(self):
        narrow_step = self.config['narrow_step'] if 'narrow_step' in self.config else 1
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            narrow_step = -narrow_step    
        self.current_value += narrow_step
        
        # Make sure the game stays interesting by not going out of a certain range
        if 'initial_min_value' in self.config and self.current_value < self.config['initial_min_value']:
            self.current_value = self.config['initial_min_value']
        if 'initial_max_value' in self.config and self.current_value > self.config['initial_max_value']:
            self.current_value = self.config['initial_max_value']

class PositionFilter(GameFilter):
    def __init__(self, seed: int = 0):
        random.seed(seed)
        self.positions = ['Guard', 'Forward', 'Center']
        self.selected_position = random.choice(self.positions)
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(position__contains=self.selected_position) # position field can contain multiple positions like 'Guard, Forward'
    def get_desc(self) -> str:
        return f"Plays {self.selected_position} position"
    def get_player_stats_str(self, player: Player) -> str:
        return f"Position: {player.position}"
    def get_detailed_desc(self) -> str:
        return f"This filter selects players who are listed as {self.selected_position}s in their position. " \
               f"Players can be listed with multiple positions, such as 'Guard, Forward', " \
               f"and will be included if any of their positions match {self.selected_position}. " \
               f"Positions are taken as listed on nba.com."

class USAFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(country="USA")
    def get_desc(self) -> str:
        return f"Born in USA"
    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who were born in the United States of America.\n\n" \
               "Players born in U.S. territories like Puerto Rico are considered international players and are excluded by this filter.\n\n" \
               "Players who gained U.S. citizenship after being born elsewhere are also excluded."

class InternationalFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.exclude(country="USA")
    def get_desc(self) -> str:
        return f"Born outside of USA"
    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who were born outside the USA, like Canada, Greenland, Mexico, Panama, etc." \
               "This also includes players born in US territories like Puerto Rico."

class CountryFilter(GameFilter):
    def __init__(self, seed: int = 0):
        random.seed(seed)
        
        # NOTE: Most countries do not have enough players for this filter to work
        #       A few results from querying in April 2025:
        #       - num_players_per_country=40: [USA]
        #       - num_players_per_country=20: ['USA', 'Canada']
        #       - num_players_per_country=10: ['USA', 'Canada', 'Australia', 'France']
        #       - num_players_per_country=5:  ['USA', 'Canada', 'Australia', 'France', 'Serbia', 'Cameroon', 'Germany']
        # For now let's keep the filter to 30 players per country, even if it's only USA players getting returned
        num_players_per_country = 30
        countries = [country for country in Player.objects.all().values_list('country', flat=True).distinct() 
                    if Player.objects.filter(country=country).count() >= num_players_per_country]
        self.country_name = random.choice(countries)
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(country=self.country_name)
    def get_desc(self) -> str:
        return f"From country: {self.country_name}"
    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"
    def get_detailed_desc(self) -> str:
        return f"This filter selects players who were born in {self.country_name}."

class TeamFilter(GameFilter):
    def __init__(self, seed: int = 0):
        random.seed(seed)
        teams = list(Team.objects.all())
        self.team_name = random.choice(teams).name
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(teams__name=self.team_name)
    def get_desc(self) -> str:
        return f"Played for {self.team_name}"
    def get_player_stats_str(self, player: Player) -> str:
        team_abbrs = [team.abbr for team in player.teams.all()]
        return f"Teams: {', '.join(team_abbrs)}"
    def get_detailed_desc(self) -> str:
        return f"This filter selects players who played for the {self.team_name} at any point in their NBA career. " \
               f"Players need to have played at least one game for the team to be included."

class BooleanFilter(GameFilter):
    '''
    This is just a stub for legacy BooleanFilter. Nowadays we just use Top10DraftpickFilter.
    '''
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players
    def get_desc(self) -> str:
        return ""
    def get_player_stats_str(self, player: Player) -> str:
        return ""
    def get_detailed_desc(self) -> str:
        return "This filter selects players who were chosen within the top 10 picks of any NBA draft. " \
               "Players who were drafted 11th or lower, or went undrafted, are excluded. "
        
class Top10DraftpickFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.exclude(is_undrafted=True).filter(draft_number__lte=10)
        
    def get_desc(self) -> str:
        return "Top 10 Draft Pick"
        
    def get_player_stats_str(self, player: Player) -> str:
        draft_pick = f"#{player.draft_number} in {player.draft_year}"
        if player.is_undrafted:
            draft_pick = "Undrafted"
        return f"Draft Pick: {draft_pick}"
    
    def get_detailed_desc(self) -> str:
        return "This filter selects players who were chosen within the top 10 picks of any NBA draft. " \
               "Players who were drafted 11th or lower, or went undrafted, are excluded. "

class AllNbaFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_nba_first=True) | players.filter(is_award_all_nba_second=True) | players.filter(is_award_all_nba_third=True)
    def get_desc(self) -> str:
        return "All-NBA player"
    def get_player_stats_str(self, player: Player) -> str:
        return f"All-NBA: {player.is_award_all_nba_first or player.is_award_all_nba_second or player.is_award_all_nba_third}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who have been named to at least one All-NBA Team (First, Second, or Third team) " \
               "during their career. Players on multiple different teams are valid as well."
    
class AllDefensiveFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_defensive=True)
    def get_desc(self) -> str:
        return "All-Defensive player"
    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Defensive: {player.is_award_all_defensive}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who have been named to at least one NBA All-Defensive Team " \
               "(First or Second) during their career."

class AllRookieFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_rookie=True)
    def get_desc(self) -> str:
        return "All-Rookie player"
    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Rookie: {player.is_award_all_rookie}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who were named to an NBA All-Rookie Team (First or Second) " \
               "in their debut season."


class NbaChampFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_champ=True)
    def get_desc(self) -> str:
        return "NBA Champion"
    def get_player_stats_str(self, player: Player) -> str:
        return f"NBA Champion: {player.is_award_champ}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who have won at least one NBA Championship during their career. " \
               "This means they were on the roster of a team that won the NBA Finals, regardless of their role " \
               "or playing time during the championship run.\n\n" \
               "'World Champion of what...?!' - Noah Lyles, World Champion"

class AllStarFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_star=True)
    def get_desc(self) -> str:
        return "All-Star player"
    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Star: {player.is_award_all_star}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who have been selected to at least one NBA All-Star Game during their career. " \
               "This is regardless of how they were selected, whether it was by fan vote, player vote, or coach vote."

class OlympicMedalFilter(GameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_olympic_gold_medal=True) | players.filter(is_award_olympic_silver_medal=True) | players.filter(is_award_olympic_bronze_medal=True)
    def get_desc(self) -> str:
        return "Olympic medalist"
    def get_player_stats_str(self, player: Player) -> str:
        return f"Olympic Medal: {player.is_award_olympic_gold_medal or player.is_award_olympic_silver_medal or player.is_award_olympic_bronze_medal}"
    def get_detailed_desc(self) -> str:
        return "This filter selects players who have won an Olympic medal (gold, silver, or bronze) " \
               "while representing their country in Olympic basketball. This includes players who competed " \
               "for Team USA as well as players who represented other countries in Olympic competition."

class TeamCountFilter(DynamicGameFilter):
    def apply_filter(self, players:Manager[Player]) -> Manager[Player]:
        # Use a subquery to count all teams, not just the ones in the current filtered queryset
        player_ids = players.values_list('stats_id', flat=True)
        
        # Get the full list of players from the DB again and count their teams
        all_matching_players = Player.objects.filter(stats_id__in=player_ids)
        all_matching_players = all_matching_players.annotate(num_teams=Count('teams', distinct=True))
        all_matching_players = all_matching_players.filter(num_teams__gte=self.current_value)
        
        # Return only the player IDs that match our criteria
        return players.filter(stats_id__in=all_matching_players.values_list('stats_id', flat=True))
    def get_desc(self) -> str:
        return f"Played for {self.current_value}+ teams"
    def get_player_stats_str(self, player: Player) -> str:
        team_abbrs = [team.abbr for team in player.teams.all()]
        return f"Teams: {len(team_abbrs)} ({', '.join(team_abbrs)})"
    def get_detailed_desc(self) -> str:
        return f"This filter selects players who have played for at least {self.current_value} different NBA teams " \
               f"during their career. This includes all franchises a player has at least one game for."

def get_dynamic_filters(seed:int=0) -> list[DynamicGameFilter]:
    random.seed(seed)
    return [
        DynamicGameFilter({
            'field': 'base_salary',
            'description': 'Salary 24/25 more than',
            'stats_desc': 'Salary 24/25:',
            'initial_min_value': 20000000,
            'initial_max_value': 40000000,
            'initial_value_step': 5000000,
            'widen_step': 5000000,
            'narrow_step': 5000000,
            'unit': 'M USD',
            'detailed_desc': 'This filter selects players with a base salary of at least the given amount for the 2024/2025 NBA season.'
        }),
        DynamicGameFilter({
            'field': 'career_ppg',
            'description': 'Career points per game:',
            'initial_min_value': 18,
            'initial_max_value': 22,
            'initial_value_step': 2,
            'widen_step': 2,
            'narrow_step': 2,
            'detailed_desc': 'This filter selects players who averaged at least a certain number of points per game (PPG). Only regular season games are considered.'
        }),
        DynamicGameFilter({
            'field': 'career_rpg',
            'description': 'Career rebounds per game:',
            'initial_min_value': 6,
            'initial_max_value': 8,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'detailed_desc': 'This filter selects players who averaged at least a certain number of rebounds per game (RPG). Only regular season games are considered.' 
        }),
        DynamicGameFilter({
            'field': 'career_apg',
            'description': 'Career assists per game:',
            'initial_min_value': 4,
            'initial_max_value': 5,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'detailed_desc': 'This filter selects players who averaged at least a certain number of assists per game (APG). Only regular season games are considered.'
        }),
        DynamicGameFilter({
            'field': 'career_gp',
            'description': 'Career games played:',
            'initial_min_value': 500,
            'initial_max_value': 600,
            'initial_value_step': 50,
            'widen_step': 50,
            'narrow_step': 50,
            'detailed_desc': 'This filter selects players who have played at least a certain number of games (GP). Only regular season games are considered. This filter excludes games where the player did not attend due to injury or other reasons.'
        }),
        DynamicGameFilter({
            'field': 'num_seasons',
            'description': 'More than ',
            'stats_desc': 'Total seasons:',
            'initial_min_value': 9,
            'initial_max_value': 11,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'comparison_type': 'higher',
            'unit': 'seasons',
            'detailed_desc': 'This filter selects players who have played at least a certain number of NBA seasons.\n\nA player is credited with a season if they appeared in at least one regular season game during that year.\n\nSuspended seasons and lockout-shortened seasons still count as full seasons.'
        }),
        DynamicGameFilter({
            'field': 'num_seasons',
            'description': 'No more than ',
            'stats_desc': 'Total seasons:',
            'initial_min_value': 1,
            'initial_max_value': 3,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'comparison_type': 'lower',
            'unit': 'seasons',
            'detailed_desc': 'This filter selects players who have played at most a certain number of NBA seasons. This includes any season where a player played at least one game. This does not include G-League or International games.'
        }),
        DynamicGameFilter({
            'field': 'height_cm',
            'description': 'Taller than',
            'stats_desc': 'Height:',
            'initial_min_value': 200,
            'initial_max_value': 210,
            'initial_value_step': 5,
            'widen_step': 5,
            'narrow_step': 5,
            'unit': 'cm',
            'comparison_type': 'higher',
            'detailed_desc': 'This filter selects players who are taller than a certain height in centimeters.'
        }),
        DynamicGameFilter({
            'field': 'height_cm',
            'description': 'Smaller than',
            'stats_desc': 'Height:',
            'initial_min_value': 190,
            'initial_max_value': 195,
            'initial_value_step': 5,
            'widen_step': 5,
            'narrow_step': 5,
            'unit': 'cm',
            'comparison_type': 'lower',
            'detailed_desc': 'This filter selects players who are shorter than a certain height in centimeters.'
        }),
        # NOTE: Weight filter was not very fun to play,
        #       as it's hard to estimate and not something
        #       a user cares about when looking at nba stats
        #DynamicGameFilter({
        #    'field': 'weight_kg',
        #    'description': 'Heavier than',
        #    'initial_min_value': 100,
        #    'initial_max_value': 120,
        #    'initial_value_step': 5,
        #    'widen_step': 5,
        #    'narrow_step': 5,
        #    'unit': 'kg'
        #}),
        DynamicGameFilter({
            'field': 'career_high_pts',
            'description': 'Career high points:',
            'initial_min_value': 40,
            'initial_max_value': 55,
            'initial_value_step': 5,
            'widen_step': 5,
            'narrow_step': 5,
            'detailed_desc': 'This filter selects players who have scored at least a certain number of points in a single game. This includes regular season and playoff games.'
        }),
        DynamicGameFilter({
            'field': 'career_high_reb',
            'description': 'Career high rebounds:',
            'initial_min_value': 15,
            'initial_max_value': 20,
            'initial_value_step': 5,
            'widen_step': 5,
            'narrow_step': 5,
            'detailed_desc': 'This filter selects players who have caught at least a certain number of rebounds in a single game. This includes regular season and playoff games.'
        }),
        DynamicGameFilter({
            'field': 'career_high_ast',
            'description': 'Career high assists:',
            'initial_min_value': 15,
            'initial_max_value': 17,
            'initial_value_step': 5,
            'widen_step': 5,
            'narrow_step': 5,
            'detailed_desc': 'This filter selects players who have passed at least a certain number of assists in a single game. This includes regular season and playoff games.'
        }),
        DynamicGameFilter({
            'field': 'career_high_stl',
            'description': 'Career high steals:',
            'initial_min_value': 5,
            'initial_max_value': 7,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'detailed_desc': 'This filter selects players who have snatched at least a certain number of steals in a single game. This includes regular season and playoff games.'
        }),
        DynamicGameFilter({
            'field': 'career_high_blk',
            'description': 'Career high blocks:',
            'initial_min_value': 5,
            'initial_max_value': 7,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'detailed_desc': 'This filter selects players who have blocked at least a certain number of shots in a single game. This includes regular season and playoff games.'
        }),
        TeamCountFilter({
            'description': 'Teams played for:',
            'initial_min_value': 5,
            'initial_max_value': 7,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1,
            'detailed_desc': 'This filter selects players who played for at least a certain number of NBA teams. This includes any team where a player played at least one game.'
        })
    ]

def get_static_filters(seed:int=0) -> list[GameFilter]:
    return [
        USAFilter(),
        InternationalFilter(),
        AllNbaFilter(),
        AllDefensiveFilter(),
        AllRookieFilter(),
        NbaChampFilter(),
        AllStarFilter(),
        OlympicMedalFilter(),
        # CountryFilter(seed), # deprecated, use USAFilter and InternationalFilter instead
        TeamFilter(seed),
        Top10DraftpickFilter(),
        PositionFilter(seed)
    ]

def create_filter_from_db(db_filter):
    """Create a GameFilter object from a database record.
    
    Args:
        db_filter: A GameFilterDB model instance from the database
        
    Returns:
        A GameFilter object of the appropriate type with the stored configuration
    """
    filter_class = globals()[db_filter.filter_class]
    config = db_filter.filter_config.copy()
    
    # Handle special cases for different filter types
    if filter_class == DynamicGameFilter or filter_class == TeamCountFilter:
        # For dynamic filters, we need to preserve the config and current_value
        current_value = config.pop('current_value', None)
        config_data = config.pop('config', config)  # Use remaining config if no 'config' key
        filter_obj = filter_class(config_data)
        if current_value is not None:
            filter_obj.current_value = current_value
        return filter_obj
    elif filter_class == TeamFilter:
        team_name = config.pop('team_name', None)
        filter_obj = filter_class(0)  # Seed doesn't matter for reconstruction
        if team_name is not None:
            filter_obj.team_name = team_name
        return filter_obj
    elif filter_class == PositionFilter:
        position = config.pop('selected_position', None)
        filter_obj = filter_class(0)  # Seed doesn't matter for reconstruction
        if position is not None:
            filter_obj.selected_position = position
        return filter_obj
    elif filter_class == USAFilter:
        return filter_class()
    elif filter_class == InternationalFilter:
        return filter_class()
    elif filter_class == CountryFilter:
        country = config.pop('country_name', None)
        filter_obj = filter_class(0)  # Seed doesn't matter for reconstruction
        if country is not None:
            filter_obj.country_name = country
        return filter_obj
    elif filter_class == BooleanFilter:
        return Top10DraftpickFilter()
    elif filter_class == Top10DraftpickFilter:
        return filter_class()
    
    # For any other filter type, just pass the config as is
    return filter_class(**config)
