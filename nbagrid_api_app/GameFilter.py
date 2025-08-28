import logging
import random
from abc import abstractmethod

from django.db.models import Count, Manager

from nbagrid_api_app.models import Player, Team

logger = logging.getLogger(__name__)


def cm_to_feet_inches(cm):
    """Convert centimeters to feet and inches format."""
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    return (feet, inches)


class GameFilter(object):
    @abstractmethod
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
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

    def get_filter_type_description(self) -> str:
        """Return a normalized type description for this filter.
        
        This should return a consistent identifier for the filter type that groups
        similar filters together (e.g., all DynamicGameFilters with the same base
        description should return the same type description).
        
        Default implementation returns the class name.
        """
        return self.__class__.__name__

    def to_json(self) -> dict:
        """Convert this filter to a JSON-serializable dictionary.
        
        Returns:
            A dictionary containing the filter's class name and configuration
        """
        return {
            "class_name": self.__class__.__name__,
            "name": self.get_desc(),
            "config": self._get_config()
        }
    
    def _get_config(self) -> dict:
        """Get the configuration dictionary for this filter.
        
        This method should be overridden by subclasses to return their specific configuration.
        
        Returns:
            A dictionary containing the filter's configuration
        """
        return {}
    
    @abstractmethod
    def _from_config(cls, config: dict) -> 'GameFilter':
        pass
    
    @classmethod
    def from_json(cls, filter_data: dict) -> 'GameFilter':
        """Create a filter instance from JSON data.
        
        Args:
            filter_data: A dictionary containing filter data with 'class_name' and 'config' keys
            
        Returns:
            A GameFilter instance of the appropriate type
            
        Raises:
            ValueError: If the filter class is not found or invalid
        """
        class_name = filter_data.get("class_name", None)
        config = filter_data.get("config", {})
        
        if not class_name:
            raise ValueError("Filter data must contain 'class_name'")
        
        # Get the filter class from globals
        filter_class = globals().get(class_name)
        if not filter_class:
            raise ValueError(f"Filter class '{class_name}' not found")
        
        # Create the filter instance
        return filter_class._from_config(config)

    def __str__(self) -> str:
        return self.get_desc()


class DynamicGameFilter(GameFilter):
    def __init__(self, config, seed: int = 0):
        self.config = config
        self.seed = seed
        self.current_value = self._get_initial_value()

    def _get_initial_value(self):
        rng = random.Random(self.seed)
        if "initial_value_step" in self.config:
            return rng.choice(
                range(self.config["initial_min_value"], self.config["initial_max_value"], self.config["initial_value_step"])
            )
        if "initial_min_value" in self.config and "initial_max_value" in self.config:
            return rng.randint(self.config["initial_min_value"], self.config["initial_max_value"])
        return 0

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        field = self.config["field"]
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            comparison_operator = "__lt"
        else:
            comparison_operator = "__gte"
        return players.filter(**{f"{field}{comparison_operator}": self.current_value})

    def get_player_stats_str(self, player: Player) -> str:
        description = self.config["stats_desc"] if "stats_desc" in self.config else self.config["description"]
        field = self.config["field"]
        stat_value = getattr(player, field)
        if stat_value > 1000000:
            stat_value = f"{stat_value / 1000000:.1f}"
        unit = f" {self.config['unit']}" if "unit" in self.config else ""

        # Special handling for height filters to show both metric and American units
        if field == "height_cm":
            feet, inches = cm_to_feet_inches(stat_value)
            return f"{description} {stat_value}{unit} ({feet}′{inches}″)"

        return f"{description} {stat_value}{unit}"

    def get_desc(self) -> str:
        description = self.config["description"]
        unit = f" {self.config['unit']}" if "unit" in self.config else ""
        desc_operator = "+"
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            desc_operator = "-"
        display_value = self.current_value
        if self.current_value > 1000000:
            display_value = f"{self.current_value / 1000000:.1f}"

        # Special handling for height filters to show both metric and American units
        if self.config["field"] == "height_cm":
            feet, inches = cm_to_feet_inches(self.current_value)
            return f"{description} {display_value}{desc_operator}{unit} ({feet}′{inches}″)"

        return f"{description} {display_value}{desc_operator}{unit}"

    def get_detailed_desc(self) -> str:
        return self.config.get("detailed_desc", f"{self.get_desc()}")

    def widen_filter(self):
        widen_step = -(self.config["widen_step"] if "widen_step" in self.config else 1)
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            widen_step = -widen_step
        self.current_value += widen_step

        # Make sure the game stays interesting by not going out of a certain range
        if "initial_min_value" in self.config and self.current_value < self.config["initial_min_value"]:
            self.current_value = self.config["initial_min_value"]
        if "initial_max_value" in self.config and self.current_value > self.config["initial_max_value"]:
            self.current_value = self.config["initial_max_value"]

    def narrow_filter(self):
        narrow_step = self.config["narrow_step"] if "narrow_step" in self.config else 1
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            narrow_step = -narrow_step
        self.current_value += narrow_step

        # Make sure the game stays interesting by not going out of a certain range
        if "initial_min_value" in self.config and self.current_value < self.config["initial_min_value"]:
            self.current_value = self.config["initial_min_value"]
        if "initial_max_value" in self.config and self.current_value > self.config["initial_max_value"]:
            self.current_value = self.config["initial_max_value"]

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this dynamic filter."""
        config = self.config.copy()
        config["current_value"] = self.current_value
        return config
    
    @classmethod
    def _from_config(cls, config: dict) -> 'DynamicGameFilter':
        """Create a DynamicGameFilter instance from configuration."""
        current_value = config.pop("current_value", None)
        filter_obj = cls(config)
        if current_value is not None:
            filter_obj.current_value = current_value
        return filter_obj

    def get_filter_type_description(self) -> str:
        """Return a normalized type description for this dynamic filter."""
        if 'field' not in self.config:
            return self.__class__.__name__
        
        field = self.config['field']
        comparison_type = self.config.get('comparison_type', 'higher')
        
        # Create a consistent type description based on field and comparison
        if comparison_type == 'lower':
            return f"{self.__class__.__name__}_{field}_lower"
        else:
            return f"{self.__class__.__name__}_{field}_higher"


class PositionFilter(GameFilter):
    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        self.positions = ["Guard", "Forward", "Center"]
        self.selected_position = rng.choice(self.positions)

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(
            position__contains=self.selected_position
        )  # position field can contain multiple positions like 'Guard, Forward'

    def get_desc(self) -> str:
        return f"Plays {self.selected_position} position"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Position: {player.position}"

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this position filter."""
        return {"selected_position": self.selected_position}
    
    @classmethod
    def _from_config(cls, config: dict) -> 'PositionFilter':
        """Create a PositionFilter instance from configuration."""
        filter_obj = cls(0)  # Seed doesn't matter for reconstruction
        if "selected_position" in config:
            filter_obj.selected_position = config["selected_position"]
        return filter_obj

    def get_detailed_desc(self) -> str:
        return (
            f"This filter selects players who are listed as {self.selected_position}s in their position. "
            f"Players can be listed with multiple positions, such as 'Guard, Forward', "
            f"and will be included if any of their positions match {self.selected_position}. "
            f"Positions are taken as listed on nba.com."
        )


class USAFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(country="USA")

    def get_desc(self) -> str:
        return f"Born in USA"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were born in the United States of America.\n\n"
            "Players born in U.S. territories like Puerto Rico are considered international players and are excluded by this filter.\n\n"
            "Players who gained U.S. citizenship after being born elsewhere are also excluded."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'USAFilter':
        """Create a USAFilter instance from configuration."""
        return cls()


class InternationalFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.exclude(country="USA")

    def get_desc(self) -> str:
        return f"Born outside of USA"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were born outside the USA, like Canada, Greenland, Mexico, Panama, etc."
            "This also includes players born in US territories like Puerto Rico."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'InternationalFilter':
        """Create an InternationalFilter instance from configuration."""
        return cls()


class EuropeanUnionFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        # List of European Union member countries as of 2024
        eu_countries = [
            "Austria",
            "Belgium",
            "Bulgaria",
            "Croatia",
            "Cyprus",
            "Czech Republic",
            "Denmark",
            "Estonia",
            "Finland",
            "France",
            "Germany",
            "Greece",
            "Hungary",
            "Ireland",
            "Italy",
            "Latvia",
            "Lithuania",
            "Luxembourg",
            "Malta",
            "Netherlands",
            "Poland",
            "Portugal",
            "Romania",
            "Slovakia",
            "Slovenia",
            "Spain",
            "Sweden",
        ]
        return players.filter(country__in=eu_countries)

    def get_desc(self) -> str:
        return f"Born in European Union"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were born in European Union member countries. "
            "This includes all 27 EU member states as of 2024: Austria, Belgium, Bulgaria, "
            "Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, "
            "Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, "
            "Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, and Sweden."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'EuropeanUnionFilter':
        """Create a EuropeanUnionFilter instance from configuration."""
        return cls()


class CountryFilter(GameFilter):
    def __init__(self, seed: int = 0):
        rng = random.Random(seed)

        # NOTE: Most countries do not have enough players for this filter to work
        #       A few results from querying in April 2025:
        #       - num_players_per_country=40: [USA]
        #       - num_players_per_country=20: ['USA', 'Canada']
        #       - num_players_per_country=10: ['USA', 'Canada', 'Australia', 'France']
        #       - num_players_per_country=5:  ['USA', 'Canada', 'Australia', 'France', 'Serbia', 'Cameroon', 'Germany']
        # For now let's keep the filter to 30 players per country, even if it's only USA players getting returned
        num_players_per_country = 30
        countries = [
            country
            for country in Player.objects.all().values_list("country", flat=True).distinct()
            if Player.objects.filter(country=country).count() >= num_players_per_country
        ]
        self.country_name = rng.choice(countries)

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(country=self.country_name)

    def get_desc(self) -> str:
        return f"From country: {self.country_name}"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Birthplace: {player.country}"

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this country filter."""
        return {"country_name": self.country_name}
    
    @classmethod
    def _from_config(cls, config: dict) -> 'CountryFilter':
        """Create a CountryFilter instance from configuration."""
        filter_obj = cls(0)  # Seed doesn't matter for reconstruction
        if "country_name" in config:
            filter_obj.country_name = config["country_name"]
        return filter_obj

    def get_detailed_desc(self) -> str:
        return f"This filter selects players who were born in {self.country_name}."


class TeamFilter(GameFilter):
    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        teams = list(Team.objects.all())
        self.team_name = rng.choice(teams).name

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(teams__name=self.team_name)

    def get_desc(self) -> str:
        return f"Played for {self.team_name}"

    def get_player_stats_str(self, player: Player) -> str:
        team_abbrs = [team.abbr for team in player.teams.all()]
        return f"Teams: {', '.join(team_abbrs)}"

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this team filter."""
        return {"team_name": self.team_name}
    
    @classmethod
    def _from_config(cls, config: dict) -> 'TeamFilter':
        """Create a TeamFilter instance from configuration."""
        filter_obj = cls(0)  # Seed doesn't matter for reconstruction
        if "team_name" in config:
            filter_obj.team_name = config["team_name"]
        return filter_obj

    def get_detailed_desc(self) -> str:
        return (
            f"This filter selects players who played for the {self.team_name} at any point in their NBA career. "
            f"Players need to have played at least one game for the team to be included."
        )


class BooleanFilter(GameFilter):
    """
    This is just a stub for legacy BooleanFilter. Nowadays we just use Top10DraftpickFilter.
    """

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players

    def get_desc(self) -> str:
        return ""

    def get_player_stats_str(self, player: Player) -> str:
        return ""

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were chosen within the top 10 picks of any NBA draft. "
            "Players who were drafted 11th or lower, or went undrafted, are excluded. "
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'BooleanFilter':
        """Create a BooleanFilter instance from configuration."""
        return Top10DraftpickFilter()


class Top10DraftpickFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.exclude(is_undrafted=True).filter(draft_number__lte=10)

    def get_desc(self) -> str:
        return "Top 10 Draft Pick"

    def get_player_stats_str(self, player: Player) -> str:
        draft_pick = f"#{player.draft_number} in {player.draft_year}"
        if player.is_undrafted:
            draft_pick = "Undrafted"
        return f"Draft Pick: {draft_pick}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were chosen within the top 10 picks of any NBA draft. "
            "Players who were drafted 11th or lower, or went undrafted, are excluded. "
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'Top10DraftpickFilter':
        """Create a Top10DraftpickFilter instance from configuration."""
        return cls()


class AllNbaFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return (
            players.filter(is_award_all_nba_first=True)
            | players.filter(is_award_all_nba_second=True)
            | players.filter(is_award_all_nba_third=True)
        )

    def get_desc(self) -> str:
        return "All-NBA player"

    def get_player_stats_str(self, player: Player) -> str:
        return f"All-NBA: {player.is_award_all_nba_first or player.is_award_all_nba_second or player.is_award_all_nba_third}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who have been named to at least one All-NBA Team (First, Second, or Third team) "
            "during their career. Players on multiple different teams are valid as well."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'AllNbaFilter':
        """Create an AllNbaFilter instance from configuration."""
        return cls()


class AllDefensiveFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_defensive=True)

    def get_desc(self) -> str:
        return "All-Defensive player"

    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Defensive: {player.is_award_all_defensive}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who have been named to at least one NBA All-Defensive Team "
            "(First or Second) during their career."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'AllDefensiveFilter':
        """Create an AllDefensiveFilter instance from configuration."""
        return cls()


class AllRookieFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_rookie=True)

    def get_desc(self) -> str:
        return "All-Rookie player"

    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Rookie: {player.is_award_all_rookie}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who were named to an NBA All-Rookie Team (First or Second) " "in their debut season."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'AllRookieFilter':
        """Create an AllRookieFilter instance from configuration."""
        return cls()


class NbaChampFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_champ=True)

    def get_desc(self) -> str:
        return "NBA Champion"

    def get_player_stats_str(self, player: Player) -> str:
        return f"NBA Champion: {player.is_award_champ}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who have won at least one NBA Championship during their career. "
            "This means they were on the roster of a team that won the NBA Finals, regardless of their role "
            "or playing time during the championship run.\n\n"
            "'World Champion of what...?!' - Noah Lyles, World Champion"
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'NbaChampFilter':
        """Create a NbaChampFilter instance from configuration."""
        return cls()


class AllStarFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return players.filter(is_award_all_star=True)

    def get_desc(self) -> str:
        return "All-Star player"

    def get_player_stats_str(self, player: Player) -> str:
        return f"All-Star: {player.is_award_all_star}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who have been selected to at least one NBA All-Star Game during their career. "
            "This is regardless of how they were selected, whether it was by fan vote, player vote, or coach vote."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'AllStarFilter':
        """Create an AllStarFilter instance from configuration."""
        return cls()


class OlympicMedalFilter(GameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        return (
            players.filter(is_award_olympic_gold_medal=True)
            | players.filter(is_award_olympic_silver_medal=True)
            | players.filter(is_award_olympic_bronze_medal=True)
        )

    def get_desc(self) -> str:
        return "Olympic medalist"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Olympic Medal: {player.is_award_olympic_gold_medal or player.is_award_olympic_silver_medal or player.is_award_olympic_bronze_medal}"

    def get_detailed_desc(self) -> str:
        return (
            "This filter selects players who have won an Olympic medal (gold, silver, or bronze) "
            "while representing their country in Olympic basketball. This includes players who competed "
            "for Team USA as well as players who represented other countries in Olympic competition."
        )
    
    @classmethod
    def _from_config(cls, config: dict) -> 'OlympicMedalFilter':
        """Create an OlympicMedalFilter instance from configuration."""
        return cls()


class LastNameFilter(GameFilter):
    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        # Get valid letters and select a random one
        valid_letters = self._get_valid_letters()
        if valid_letters:
            self.selected_letter = rng.choice(valid_letters)
        else:  # This is only the case when running within the context of a test
            self.selected_letter = "A"

    def _get_valid_letters(self):
        """Helper method to get sorted list of valid letters with sufficient players"""
        # Count players per starting letter using the last_name field
        letter_counts = {}
        for last_name in Player.objects.values_list("last_name", flat=True):
            if last_name:
                first_letter = last_name[0].upper()
                letter_counts[first_letter] = letter_counts.get(first_letter, 0) + 1

        # Only use letters that have at least 10 players
        valid_letters = [letter for letter, count in letter_counts.items() if count >= 10]
        valid_letters.sort()
        return valid_letters

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        # Filter players whose last name starts with the selected letter (case-insensitive)
        return players.filter(last_name__istartswith=self.selected_letter)

    def get_desc(self) -> str:
        return f"Last name starts with '{self.selected_letter}'"

    def get_player_stats_str(self, player: Player) -> str:
        return f"Name: {player.last_name}"

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this last name filter."""
        return {"selected_letter": self.selected_letter}
    
    @classmethod
    def _from_config(cls, config: dict) -> 'LastNameFilter':
        """Create a LastNameFilter instance from configuration."""
        filter_obj = cls(0)  # Seed doesn't matter for reconstruction
        if "selected_letter" in config:
            filter_obj.selected_letter = config["selected_letter"]
        return filter_obj

    def get_detailed_desc(self) -> str:
        return f"This filter selects players whose last name starts with the letter '{self.selected_letter}'. "


class PlayedWithPlayerFilter(GameFilter):
    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        # Get a random player who has been an All-Star and has teammates
        all_star_players_with_teammates = Player.objects.filter(
            is_award_all_star=True,
            teammates__isnull=False
        ).distinct()
        
        if all_star_players_with_teammates.exists():
            self.target_player = rng.choice(all_star_players_with_teammates)
        else:
            # Fallback to any All-Star player if no teammates data exists yet
            all_star_players = Player.objects.filter(is_award_all_star=True)
            if all_star_players.exists():
                self.target_player = rng.choice(all_star_players)
            else:
                # Ultimate fallback to any player if no All-Stars exist
                self.target_player = rng.choice(list(Player.objects.all()))

    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        # Get players who have played with the target player
        return players.filter(teammates=self.target_player)

    def get_desc(self) -> str:
        return f"Played with {self.target_player.name}"

    def get_player_stats_str(self, player: Player) -> str:
        # Show which teams they played together on
        common_teams = player.teams.intersection(self.target_player.teams.all())
        team_abbrs = [team.abbr for team in common_teams]
        if team_abbrs:
            return f"Played together on: {', '.join(team_abbrs)}"
        else:
            return f"Teammate of {self.target_player.name}"

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this played with player filter."""
        return {"target_player": self.target_player.name}
    
    @classmethod
    def _from_config(cls, config: dict) -> 'PlayedWithPlayerFilter':
        """Create a PlayedWithPlayerFilter instance from configuration."""
        filter_obj = cls(0)  # Seed doesn't matter for reconstruction
        if "target_player" in config:
            try:
                filter_obj.target_player = Player.objects.get(name=config["target_player"])
            except Player.DoesNotExist:
                # If target player doesn't exist, keep the randomly selected one
                pass
        return filter_obj

    def get_detailed_desc(self) -> str:
        return (
            f"This filter selects players who have played together with {self.target_player.name} "
            f"at any point during their careers. This only counts players who have been part of the same "
            f"lineup, not just players who were on the same team but never played together."
        )


class TeamCountFilter(DynamicGameFilter):
    def apply_filter(self, players: Manager[Player]) -> Manager[Player]:
        # Use a subquery to count all teams, not just the ones in the current filtered queryset
        player_ids = players.values_list("stats_id", flat=True)

        # Get the full list of players from the DB again and count their teams
        all_matching_players = Player.objects.filter(stats_id__in=player_ids)
        all_matching_players = all_matching_players.annotate(num_teams=Count("teams", distinct=True))

        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            all_matching_players = all_matching_players.filter(num_teams__lte=self.current_value)
        else:
            all_matching_players = all_matching_players.filter(num_teams__gte=self.current_value)

        # Return only the player IDs that match our criteria
        return players.filter(stats_id__in=all_matching_players.values_list("stats_id", flat=True))

    def get_desc(self) -> str:
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            return f"Played for {self.current_value} or fewer teams"
        else:
            return f"Played for {self.current_value}+ teams"

    def get_player_stats_str(self, player: Player) -> str:
        team_abbrs = [team.abbr for team in player.teams.all()]
        return f"Teams: {len(team_abbrs)} ({', '.join(team_abbrs)})"

    def get_detailed_desc(self) -> str:
        if "comparison_type" in self.config and self.config["comparison_type"] == "lower":
            comparison_str = "at most"
        else:
            comparison_str = "at least"
        return (
            f"This filter selects players who have played for {comparison_str} {self.current_value} different NBA teams "
            f"during their career. This includes all franchises a player has at least one game for."
        )

    def _get_config(self) -> dict:
        """Get the configuration dictionary for this team count filter."""
        config = self.config.copy()
        config["current_value"] = self.current_value
        return config
    
    @classmethod
    def _from_config(cls, config: dict) -> 'TeamCountFilter':
        """Create a TeamCountFilter instance from configuration."""
        current_value = config.pop("current_value", None)
        filter_obj = cls(config)
        if current_value is not None:
            filter_obj.current_value = current_value
        return filter_obj

    def get_filter_type_description(self) -> str:
        """Return a normalized type description for team count filters."""
        # TeamCountFilter doesn't use a field, it counts teams directly
        comparison_type = self.config.get('comparison_type', 'higher')
        
        if comparison_type == 'lower':
            return f"{self.__class__.__name__}_teams_lower"
        else:
            return f"{self.__class__.__name__}_teams_higher"


def get_dynamic_filters(seed: int = 0) -> list[DynamicGameFilter]:
    return [
        DynamicGameFilter(
            {
                "field": "base_salary",
                "description": "Salary 24/25 more than",
                "stats_desc": "Salary 24/25:",
                "initial_min_value": 20000000,
                "initial_max_value": 40000000,
                "initial_value_step": 5000000,
                "widen_step": 5000000,
                "narrow_step": 5000000,
                "unit": "M USD",
                "detailed_desc": "This filter selects players with a base salary of at least the given amount for the 2024/2025 NBA season. Thanks to BBoe for suggesting this filter!",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_ppg",
                "description": "Career points per game:",
                "initial_min_value": 18,
                "initial_max_value": 26,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who averaged at least a certain number of points per game (PPG). Only regular season games are considered.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_rpg",
                "description": "Career rebounds per game:",
                "initial_min_value": 6,
                "initial_max_value": 10,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who averaged at least a certain number of rebounds per game (RPG). Only regular season games are considered.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_apg",
                "description": "Career assists per game:",
                "initial_min_value": 4,
                "initial_max_value": 10,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who averaged at least a certain number of assists per game (APG). Only regular season games are considered.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_gp",
                "description": "Career games played:",
                "initial_min_value": 500,
                "initial_max_value": 1000,
                "initial_value_step": 50,
                "widen_step": 50,
                "narrow_step": 50,
                "detailed_desc": "This filter selects players who have played at least a certain number of games (GP). Only regular season games are considered. This filter excludes games where the player did not attend due to injury or other reasons.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "num_seasons",
                "description": "More than ",
                "stats_desc": "Total seasons:",
                "initial_min_value": 9,
                "initial_max_value": 15,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "comparison_type": "higher",
                "unit": "seasons",
                "detailed_desc": "This filter selects players who have played at least a certain number of NBA seasons.\n\nA player is credited with a season if they appeared in at least one regular season game during that year.\n\nSuspended seasons and lockout-shortened seasons still count as full seasons.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "num_seasons",
                "description": "No more than ",
                "stats_desc": "Total seasons:",
                "initial_min_value": 1,
                "initial_max_value": 3,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "comparison_type": "lower",
                "unit": "seasons",
                "detailed_desc": "This filter selects players who have played at most a certain number of NBA seasons. This includes any season where a player played at least one game. This does not include G-League or International games.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "height_cm",
                "description": "Taller than",
                "stats_desc": "Height:",
                "initial_min_value": 200,
                "initial_max_value": 210,
                "initial_value_step": 5,
                "widen_step": 5,
                "narrow_step": 5,
                "unit": "cm",
                "comparison_type": "higher",
                "detailed_desc": "This filter selects players who are taller than a certain height in centimeters.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "height_cm",
                "description": "Smaller than",
                "stats_desc": "Height:",
                "initial_min_value": 180,
                "initial_max_value": 195,
                "initial_value_step": 5,
                "widen_step": 5,
                "narrow_step": 5,
                "unit": "cm",
                "comparison_type": "lower",
                "detailed_desc": "This filter selects players who are shorter than a certain height in centimeters.",
            }, seed=seed
        ),
        # NOTE: Weight filter was not very fun to play,
        #       as it's hard to estimate and not something
        #       a user cares about when looking at nba stats
        # DynamicGameFilter({
        #    'field': 'weight_kg',
        #    'description': 'Heavier than',
        #    'initial_min_value': 100,
        #    'initial_max_value': 120,
        #    'initial_value_step': 5,
        #    'widen_step': 5,
        #    'narrow_step': 5,
        #    'unit': 'kg'
        # }),
        DynamicGameFilter(
            {
                "field": "career_high_pts",
                "description": "Career high points:",
                "initial_min_value": 40,
                "initial_max_value": 60,
                "initial_value_step": 5,
                "widen_step": 5,
                "narrow_step": 5,
                "detailed_desc": "This filter selects players who have scored at least a certain number of points in a single game. This includes regular season and playoff games.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_high_reb",
                "description": "Career high rebounds:",
                "initial_min_value": 15,
                "initial_max_value": 25,
                "initial_value_step": 5,
                "widen_step": 5,
                "narrow_step": 5,
                "detailed_desc": "This filter selects players who have caught at least a certain number of rebounds in a single game. This includes regular season and playoff games.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_high_ast",
                "description": "Career high assists:",
                "initial_min_value": 15,
                "initial_max_value": 25,
                "initial_value_step": 5,
                "widen_step": 5,
                "narrow_step": 5,
                "detailed_desc": "This filter selects players who have passed at least a certain number of assists in a single game. This includes regular season and playoff games.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_high_stl",
                "description": "Career high steals:",
                "initial_min_value": 5,
                "initial_max_value": 10,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who have snatched at least a certain number of steals in a single game. This includes regular season and playoff games.",
            }, seed=seed
        ),
        DynamicGameFilter(
            {
                "field": "career_high_blk",
                "description": "Career high blocks:",
                "initial_min_value": 5,
                "initial_max_value": 10,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who have blocked at least a certain number of shots in a single game. This includes regular season and playoff games.",
            }, seed=seed
        ),
        TeamCountFilter(
            {
                "description": "Teams played for:",
                "initial_min_value": 5,
                "initial_max_value": 10,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "detailed_desc": "This filter selects players who played for at least a certain number of NBA teams. This includes any team where a player played at least one game.",
            }, seed=seed
        ),
        TeamCountFilter(
            {
                "description": "Teams played for:",
                "initial_min_value": 1,
                "initial_max_value": 3,
                "initial_value_step": 1,
                "widen_step": 1,
                "narrow_step": 1,
                "comparison_type": "lower",
                "detailed_desc": "This filter selects players who played for at most a certain number of NBA teams. This includes any team where a player played at least one game.",
            }, seed=seed
        ),
    ]


def get_static_filters(seed: int = 0) -> list[GameFilter]:
    return [
        USAFilter(),
        InternationalFilter(),
        EuropeanUnionFilter(),
        AllNbaFilter(),
        AllDefensiveFilter(),
        AllRookieFilter(),
        NbaChampFilter(),
        AllStarFilter(),
        OlympicMedalFilter(),
        # CountryFilter(seed), # deprecated, use USAFilter and InternationalFilter instead
        TeamFilter(seed),
        Top10DraftpickFilter(),
        PositionFilter(seed),
        LastNameFilter(seed),
        PlayedWithPlayerFilter(seed),
    ]



