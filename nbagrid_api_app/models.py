import logging
from datetime import timedelta

from django_prometheus.models import ExportModelOperationsMixin
from nba_api.stats.endpoints import commonplayerinfo, playerawards, playercareerstats

from django.db import models
from django.utils import timezone

from nbagrid_api_app.tracing import trace_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Player(ExportModelOperationsMixin("player"), models.Model):
    stats_id = models.IntegerField()

    # Player data
    name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=100, default="")
    display_name = models.CharField(max_length=200, default="")
    teams = models.ManyToManyField("Team")
    teammates = models.ManyToManyField("self", blank=True, help_text="Players this player has played with on the same team")
    draft_year = models.IntegerField(default=0)
    draft_round = models.IntegerField(default=0)
    draft_number = models.IntegerField(default=0)
    is_undrafted = models.BooleanField(default=False)
    is_greatest_75 = models.BooleanField(default=False)
    num_seasons = models.IntegerField(default=0)
    weight_kg = models.IntegerField(default=0)
    height_cm = models.IntegerField(default=0)
    country = models.CharField(max_length=100, default="")
    position = models.CharField(max_length=20, default="")
    base_salary = models.IntegerField(default=0)  # Base salary in USD

    # Player Stats
    career_gp = models.IntegerField(default=0)
    career_gs = models.IntegerField(default=0)
    career_min = models.IntegerField(default=0)

    # Career Highs
    career_high_ast = models.IntegerField(default=0)
    career_high_reb = models.IntegerField(default=0)
    career_high_stl = models.IntegerField(default=0)
    career_high_blk = models.IntegerField(default=0)
    career_high_to = models.IntegerField(default=0)
    career_high_pts = models.IntegerField(default=0)
    career_high_fg = models.IntegerField(default=0)
    career_high_3p = models.IntegerField(default=0)
    career_high_ft = models.IntegerField(default=0)

    # Career Averages per game
    career_apg = models.FloatField(default=0.0)
    career_ppg = models.FloatField(default=0.0)
    career_rpg = models.FloatField(default=0.0)
    career_bpg = models.FloatField(default=0.0)
    career_spg = models.FloatField(default=0.0)
    career_tpg = models.FloatField(default=0.0)
    career_fgp = models.FloatField(default=0.0)
    career_3gp = models.FloatField(default=0.0)
    career_ftp = models.FloatField(default=0.0)
    career_fga = models.FloatField(default=0.0)
    career_3pa = models.FloatField(default=0.0)
    career_fta = models.FloatField(default=0.0)

    # Awards
    is_award_mip = models.BooleanField(default=False)  # NBA Most Improved Player
    is_award_champ = models.BooleanField(default=False)  # NBA Champion
    is_award_dpoy = models.BooleanField(default=False)  # NBA Defensive Player of the Year
    is_award_all_nba_first = models.BooleanField(default=False)  # All-NBA
    is_award_all_nba_second = models.BooleanField(default=False)  # All-NBA
    is_award_all_nba_third = models.BooleanField(default=False)  # All-NBA
    is_award_all_rookie = models.BooleanField(default=False)  # All-Rookie Team
    is_award_all_defensive = models.BooleanField(default=False)  # All-Defensive Team
    is_award_all_star = models.BooleanField(default=False)  # NBA All-Star
    is_award_all_star_mvp = models.BooleanField(default=False)  # NBA All-Star Most Valuable Player
    is_award_rookie_of_the_year = models.BooleanField(default=False)  # NBA Rookie of the Year
    is_award_mvp = models.BooleanField(default=False)  # NBA Most Valuable Player
    is_award_finals_mvp = models.BooleanField(default=False)  # NBA Finals Most Valuable Player
    is_award_olympic_gold_medal = models.BooleanField(default=False)  # Olympic Gold Medal
    is_award_olympic_silver_medal = models.BooleanField(default=False)  # Olympic Silver Medal
    is_award_olympic_bronze_medal = models.BooleanField(default=False)  # Olympic Bronze Medal

    def __str__(self):
        return self.name

    @classmethod
    def generate_random_name(cls, seed_string):
        """
        Generate a random player name by combining first and last names from existing players.
        Uses the seed_string to ensure consistent results for the same input.

        Args:
            seed_string: String to use as seed for random name generation

        Returns:
            A string containing a random player name (max 14 chars)
        """
        import hashlib
        import random

        # Use the seed string to generate a deterministic random seed
        seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest(), 16)
        rng = random.Random(seed_hash)

        # Get all unique first and last names from players
        all_names = cls.objects.values_list("name", flat=True)
        first_names = set()
        last_names = set()

        for name in all_names:
            parts = name.split()
            if len(parts) >= 2:
                first_names.add(parts[0])
                last_names.add(parts[-1])

        # Generate combinations until we find one that fits
        max_attempts = 10
        for _ in range(max_attempts):
            first = rng.choice(list(first_names))
            last = rng.choice(list(last_names))
            combined = f"{first} {last}"

            if len(combined) <= 14:
                return combined

        # If we couldn't find a short enough combination, truncate the last one
        return combined[:14]

    def has_played_for_team(self, abbr):
        return self.teams.filter(abbr=abbr).exists()

    def update_player_awards_from_nba_stats(self):
        awards = playerawards.PlayerAwards(player_id=self.stats_id).get_normalized_dict()
        for award in awards["PlayerAwards"]:
            award_name = award["DESCRIPTION"]
            if award_name == "NBA Most Improved Player":
                self.is_award_mip = True
            elif award_name == "NBA Champion":
                self.is_award_champ = True
            elif award_name == "NBA Defensive Player of the Year":
                self.is_award_dpoy = True
            elif award_name == "All-NBA":
                if award["ALL_NBA_TEAM_NUMBER"] == "1":
                    self.is_award_all_nba_first = True
                elif award["ALL_NBA_TEAM_NUMBER"] == "2":
                    self.is_award_all_nba_second = True
                elif award["ALL_NBA_TEAM_NUMBER"] == "3":
                    self.is_award_all_nba_third = True
            elif award_name == "All-Rookie Team":
                self.is_award_all_rookie = True
            elif award_name == "All-Defensive Team":
                self.is_award_all_defensive = True
            elif award_name == "NBA All-Star":
                self.is_award_all_star = True
            elif award_name == "NBA All-Star Most Valuable Player":
                self.is_award_all_star_mvp = True
            elif award_name == "NBA Rookie of the Year":
                self.is_award_rookie_of_the_year = True
            elif award_name == "NBA Most Valuable Player":
                self.is_award_mvp = True
            elif award_name == "NBA Finals Most Valuable Player":
                self.is_award_finals_mvp = True
            elif award_name == "Olympic Gold Medal":
                self.is_award_olympic_gold_medal = True
            elif award_name == "Olympic Silver Medal":
                self.is_award_olympic_silver_medal = True
            elif award_name == "Olympic Bronze Medal":
                self.is_award_olympic_bronze_medal = True
        self.save()

    def update_player_data_from_nba_stats(self):
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=self.stats_id).get_normalized_dict()
        draft_year = player_info["CommonPlayerInfo"][0]["DRAFT_YEAR"]
        draft_year = 0 if (draft_year == "Undrafted") else int(draft_year)
        draft_round = player_info["CommonPlayerInfo"][0]["DRAFT_ROUND"]
        draft_round = 0 if ((not draft_round) or (draft_round == "Undrafted")) else int(draft_round)
        draft_number = player_info["CommonPlayerInfo"][0]["DRAFT_NUMBER"]
        draft_number = 0 if ((not draft_number) or draft_number == "Undrafted") else int(draft_number)
        self.draft_year = draft_year
        self.draft_round = draft_round
        self.draft_number = draft_number
        self.is_undrafted = True if (draft_round + draft_number == 0) else False
        self.is_greatest_75 = True if (player_info["CommonPlayerInfo"][0]["GREATEST_75_FLAG"] == "Y") else False
        self.num_seasons = player_info["CommonPlayerInfo"][0]["SEASON_EXP"]
        weight = player_info["CommonPlayerInfo"][0]["WEIGHT"]
        weight = 0 if not weight else int(weight)  # some players have '' as their weight
        if weight == 0:
            logger.info(f"Player {self.name} has no weight!!")
        self.weight_kg = self.convert_lbs_to_kg(weight)
        self.height_cm = self.convert_height_to_cm(player_info["CommonPlayerInfo"][0]["HEIGHT"])
        self.country = player_info["CommonPlayerInfo"][0]["COUNTRY"]
        self.position = player_info["CommonPlayerInfo"][0]["POSITION"]
        self.save()

    def update_player_stats_from_nba_stats(self):
        player_stats = playercareerstats.PlayerCareerStats(
            player_id=self.stats_id, per_mode36="PerGame", league_id_nullable="00"
        ).get_normalized_dict()
        for season in player_stats["SeasonTotalsRegularSeason"]:
            season_team_id = season["TEAM_ID"]
            if Team.objects.filter(stats_id=season_team_id).exists():
                self.teams.add(Team.objects.get(stats_id=season_team_id))

        if player_stats["CareerTotalsRegularSeason"]:
            career_totals = player_stats["CareerTotalsRegularSeason"][0]
            self.career_gp = career_totals["GP"]
            self.career_gs = career_totals["GS"]
            self.career_min = career_totals["MIN"]
            self.career_apg = career_totals["AST"]
            self.career_ppg = career_totals["PTS"]
            self.career_rpg = career_totals["REB"]
            self.career_bpg = career_totals["BLK"]
            self.career_spg = career_totals["STL"]
            self.career_tpg = career_totals["TOV"]
            self.career_fgp = career_totals["FG_PCT"]
            self.career_3gp = career_totals["FG3_PCT"]
            self.career_ftp = career_totals["FT_PCT"]
            self.career_fga = career_totals["FGA"]
            self.career_3pa = career_totals["FG3A"]
            self.career_fta = career_totals["FTA"]
        else:
            logger.info(f"Player {self.name} has no stats, probably a GLeague player...")

        if "CareerHighs" in player_stats:
            career_highs = player_stats["CareerHighs"]
            for high in career_highs:
                if "STAT_VALUE" not in high:
                    logger.info(f"Player {self.name} has invalid career high record, skipping...")
                    continue
                stat_value = high["STAT_VALUE"]
                if high["STAT"] == "PTS" and stat_value > self.career_high_pts:
                    self.career_high_pts = stat_value
                elif high["STAT"] == "AST" and stat_value > self.career_high_ast:
                    self.career_high_ast = stat_value
                elif high["STAT"] == "REB" and stat_value > self.career_high_reb:
                    self.career_high_reb = stat_value
                elif high["STAT"] == "STL" and stat_value > self.career_high_stl:
                    self.career_high_stl = stat_value
                elif high["STAT"] == "BLK" and stat_value > self.career_high_blk:
                    self.career_high_blk = stat_value
                elif high["STAT"] == "TOV" and stat_value > self.career_high_to:
                    self.career_high_to = stat_value
                elif high["STAT"] == "FGM" and stat_value > self.career_high_fg:
                    self.career_high_fg = stat_value
                elif high["STAT"] == "FG3M" and stat_value > self.career_high_3p:
                    self.career_high_3p = stat_value
                elif high["STAT"] == "FTA" and stat_value > self.career_high_ft:
                    self.career_high_ft = stat_value
        else:
            logger.info(f"Player {self.name} has no recorded career highs...")

        self.save()

    def load_from_nba_api(self):
        """
        Load complete player data from NBA API including basic info, stats, and awards.
        This is a convenience method that calls all the individual update methods.
        """
        try:
            self.update_player_data_from_nba_stats()
            self.update_player_stats_from_nba_stats()
            self.update_player_awards_from_nba_stats()
            logger.info(f"Successfully loaded NBA API data for player {self.name}")
        except Exception as e:
            logger.error(f"Failed to load NBA API data for player {self.name}: {e}")
            raise

    def convert_lbs_to_kg(self, weight_lbs: int) -> int:
        return weight_lbs * 0.453592

    def convert_height_to_cm(self, height_str: str) -> int:
        feet = int(height_str.split("-")[0])
        inches = int(height_str.split("-")[1])
        return (feet * 12 + inches) * 2.54

    def populate_teammates(self):
        """
        Populate the teammates field using NBA API LeagueDashLineups data to get accurate teammate information
        with proper timeframes. This method uses actual lineup data to determine who played together.
        
        APPROACH:
        1. Get the player's career stats to see which teams they played for in each season
        2. For each team/season, call LeagueDashLineups API to get all lineup combinations
        3. Parse GROUP_ID to extract player IDs who played together in lineups
        4. This gives us actual teammates who were on the court together
        
        ADVANTAGES:
        - Uses actual lineup data (who played together on court)
        - More accurate than roster-based approaches
        - Handles trades and mid-season roster changes
        
        Returns:
            A list of actual teammates found
        """
        from .nba_api_wrapper import get_player_career_stats, get_league_dash_lineups
        
        # Get the player's career stats to see which teams they played for in each season
        career_data = get_player_career_stats(self.stats_id, per_mode36="PerGame")
        
        if 'SeasonTotalsRegularSeason' not in career_data:
            logger.warning(f"No season totals found for {self.name}")
            return []
        
        all_teammates = set()
        
        # Process each season
        for season_data in career_data['SeasonTotalsRegularSeason']:
            season_id = season_data.get('SEASON_ID', '')
            team_id = season_data.get('TEAM_ID', '')
            team_abbr = season_data.get('TEAM_ABBREVIATION', '')
            games_played = season_data.get('GP', 0)
            
            # Skip total entries and seasons with no games
            if team_id == 0 or games_played == 0:
                continue
            
            logger.debug(f"Processing {self.name} - Season {season_id}, Team {team_abbr}, Games: {games_played}")
            
            try:
                # Get team lineups for this season using LeagueDashLineups API (returns more lineups)
                lineups_data = get_league_dash_lineups(
                    team_id=int(team_id), 
                    season=season_id,
                    group_quantity="5",
                    per_mode_detailed="PerGame"
                )
                
                lineups = lineups_data.get('Lineups', [])
                logger.debug(f"Found {len(lineups)} lineups for {team_abbr} in {season_id}")
                
                # Process each lineup to find teammates
                for lineup in lineups:
                    group_id = lineup.get('GROUP_ID', '')
                    games_played_together = lineup.get('GP', 0)
                    
                    # Skip lineups with no games played together
                    if games_played_together == 0:
                        continue
                    
                    # Parse GROUP_ID to extract player IDs
                    if group_id and group_id.startswith('-') and group_id.endswith('-'):
                        # Remove leading and trailing dashes, then split by dash
                        player_ids_str = group_id[1:-1]
                        player_ids = player_ids_str.split('-')
                        
                        # Convert to integers and filter out invalid IDs
                        valid_player_ids = []
                        for pid in player_ids:
                            if pid.isdigit():
                                valid_player_ids.append(int(pid))
                        
                        # Check if our player is in this lineup
                        if self.stats_id in valid_player_ids:
                            # Add all other players in this lineup as teammates
                            for teammate_id in valid_player_ids:
                                if teammate_id != self.stats_id:
                                    try:
                                        teammate = Player.objects.get(stats_id=teammate_id)
                                        all_teammates.add(teammate)
                                        logger.debug(f"Found teammate: {teammate.name} (played {games_played_together} games together in {season_id})")
                                    except Player.DoesNotExist:
                                        #logger.debug(f"Teammate with stats_id {teammate_id} not found in database")
                                        continue
                                    
            except Exception as e:
                logger.warning(f"Error getting lineups for {team_abbr} in {season_id}: {e}")
                continue
        
        # Clear existing teammates and add new ones
        self.teammates.clear()
        if all_teammates:
            self.teammates.add(*all_teammates)
            logger.info(f"Found {len(all_teammates)} teammates for {self.name}")
        else:
            logger.warning(f"No teammates found for {self.name}")
                    
        return list(all_teammates)
           
class Team(ExportModelOperationsMixin("team"), models.Model):
    stats_id = models.IntegerField()
    name = models.CharField(max_length=200)
    abbr = models.CharField(max_length=3)

    def __str__(self):
        return f"{self.abbr} {self.name}" if self.abbr else self.name


class GameResult(ExportModelOperationsMixin("gameresult"), models.Model):
    date = models.DateField()
    cell_key = models.CharField(max_length=10)  # e.g., "0_1" for row 0, col 1
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    guess_count = models.IntegerField(default=1)  # Number of times this player was correctly guessed for this cell
    initial_guesses = models.IntegerField(default=0)  # Number of initial guesses set during grid initialization
    wrong_guesses = models.IntegerField(default=0)  # Number of times this player was incorrectly guessed for this cell

    class Meta:
        unique_together = ["date", "cell_key", "player"]  # Ensure we can track multiple correct players per cell

    @property
    def user_guesses(self):
        """Calculate the number of actual user guesses by subtracting initial guesses from total guess count."""
        return max(0, self.guess_count - self.initial_guesses)

    @classmethod
    def get_cell_stats(cls, date, cell_key):
        """Get all correct players and their guess counts for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key).select_related("player")

    @classmethod
    def get_most_common_players(cls, date, cell_key, limit=5):
        """Get the most commonly guessed players for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key).select_related("player").order_by("-guess_count")[:limit]

    @classmethod
    def get_rarest_players(cls, date, cell_key, limit=5):
        """Get the rarest correct guesses for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key).select_related("player").order_by("guess_count")[:limit]

    @classmethod
    @trace_operation("GameResult.get_total_guesses")
    def get_total_guesses(cls, date):
        """Get the total number of correct guesses for a specific date."""
        return cls.objects.filter(date=date).aggregate(total=models.Sum("guess_count"))["total"] or 0

    @classmethod
    @trace_operation("GameResult.get_total_user_guesses")
    def get_total_user_guesses(cls, date):
        """Get the total number of user guesses (excluding initial guesses) for a specific date."""
        results = cls.objects.filter(date=date).values('guess_count', 'initial_guesses')
        total_user_guesses = 0
        for result in results:
            user_guesses = max(0, result['guess_count'] - result['initial_guesses'])
            total_user_guesses += user_guesses
        return total_user_guesses

    @classmethod
    @trace_operation("GameResult.get_total_wrong_guesses")
    def get_total_wrong_guesses(cls, date):
        """Get the total number of wrong guesses for a specific date."""
        return cls.objects.filter(date=date).aggregate(total=models.Sum("wrong_guesses"))["total"] or 0

    @classmethod
    @trace_operation("GameResult.record_wrong_guess")
    def record_wrong_guess(cls, date, cell_key, player):
        """Record a wrong guess for a player in a specific cell on a specific date."""
        result, created = cls.objects.get_or_create(
            date=date, 
            cell_key=cell_key, 
            player=player,
            defaults={"wrong_guesses": 1}
        )
        
        if not created:
            result.wrong_guesses += 1
            result.save()
        
        return result

    @classmethod
    @trace_operation("GameResult.get_player_rarity_score")
    def get_player_rarity_score(cls, date, cell_key, player):
        """Calculate a rarity score for a player in a specific cell on a specific date.
        Score is between 0 and 1, where 1 is the rarest (least guessed) and 0 is the most common.
        Returns 1.0 for first-time guesses on that date."""
        try:
            # Check if this player has been guessed for this cell on this date
            result = cls.objects.get(date=date, cell_key=cell_key, player=player)
            # If this is the first guess for this player in this cell, return 1.0
            if result.guess_count == 1:
                return 1.0
            # Get total guesses for this cell on this date
            total_guesses = (
                cls.objects.filter(date=date, cell_key=cell_key).aggregate(total=models.Sum("guess_count"))["total"] or 1
            )
            return 1 - (result.guess_count / total_guesses)
        except cls.DoesNotExist:
            return 1.0  # Player hasn't been guessed yet for this cell on this date

    @classmethod
    @trace_operation("GameResult.initialize_scores_from_recent_games")
    def initialize_scores_from_recent_games(cls, date, cell_key, num_games=5, game_factor=5, filters=[]):
        """Initialize GameResult entries for players based on their historical pick frequency.
        For each cell, we:
        1. Get all possible players for that cell (filtered by any provided filters)
        2. Count how many times each player has been picked in the past
        3. Rank players by their pick count (decreasing)
        4. Initialize guess_count based on rank (multiplied by game_factor)
        5. Set guess_count to 0 for players that haven't been picked in the past
        6. Set guess_count to 0 for bottom third of players

        Args:
            date: The date to initialize scores for
            cell_key: The cell key to initialize scores for
            num_games: Number of recent games to look back at (unused in new implementation)
            game_factor: Factor to multiply the rank by for guess_count
            filters: List of filters to apply to possible players
        """
        logger.debug(f"Initializing scores for date {date}, cell {cell_key}")

        # Get all possible players for this cell
        possible_players = Player.objects.all()

        # Apply any filters
        if filters:
            logger.debug(f"Applying {len(filters)} filters to possible players")
            for f in filters:
                logger.debug(f"Applying filter '{f.get_desc()}'")
                possible_players = f.apply_filter(possible_players)

        # Get historical pick counts for each player
        player_counts = {}
        for player in possible_players:
            # Count total picks for this player across all cells and dates
            count = cls.objects.filter(player=player).aggregate(total=models.Sum("guess_count"))["total"] or 0
            player_counts[player] = count

        # Sort players by count (decreasing)
        sorted_players = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)

        # Calculate cutoff for bottom third
        total_players = len(sorted_players)
        bottom_third_cutoff = total_players // 3

        # Initialize scores based on rank
        for rank, (player, _) in enumerate(sorted_players, 1):
            # Calculate initial_guesses based on rank
            is_bottom_third = rank >= (total_players - bottom_third_cutoff)
            has_counted_games = player_counts[player] >= 0
            if (not is_bottom_third) and has_counted_games:
                initial_guesses = (total_players - rank + 1) * game_factor
                guess_count = initial_guesses
            else:
                initial_guesses = 0
                guess_count = 0

            logger.debug(f"Setting player {player.name} initial_guesses to {initial_guesses} (rank {rank})")

            # Create or update GameResult entry with both initial_guesses and guess_count
            cls.objects.update_or_create(
                date=date, 
                cell_key=cell_key, 
                player=player, 
                defaults={
                    "initial_guesses": initial_guesses,
                    "guess_count": initial_guesses  # Initially, guess_count equals initial_guesses
                }
            )

    def __str__(self):
        return f"{self.date} - {self.cell_key} - {self.player.name} ({self.guess_count} correct, {self.initial_guesses} initial, {self.user_guesses} user, {self.wrong_guesses} wrong)"

    @classmethod
    @trace_operation("GameResult.get_player_ranking_by_guesses")
    def get_player_ranking_by_guesses(cls):
        """Get a ranking of all players sorted by their total guess count across all games.
        Returns a list of tuples (player, total_guesses, total_user_guesses, total_wrong_guesses)."""
        from django.db.models import Sum
        
        # Get all players with their total guess counts
        player_stats = cls.objects.values('player_id').annotate(
            total_guesses=Sum('guess_count'),
            total_initial_guesses=Sum('initial_guesses'),
            total_wrong_guesses=Sum('wrong_guesses')
        ).order_by('-total_guesses')
        
        # Convert to list of tuples for easier processing
        ranking = []
        for stat in player_stats:
            try:
                player = Player.objects.get(id=stat['player_id'])
                total_guesses = stat['total_guesses'] or 0
                total_initial_guesses = stat['total_initial_guesses'] or 0
                total_wrong_guesses = stat['total_wrong_guesses'] or 0
                
                # Calculate user guesses (total - initial)
                total_user_guesses = max(0, total_guesses - total_initial_guesses)
                
                ranking.append((player, total_guesses, total_user_guesses, total_wrong_guesses))
            except Player.DoesNotExist:
                # Skip if player doesn't exist
                continue
        
        return ranking

    @classmethod
    @trace_operation("GameResult.get_player_ranking_by_user_guesses")
    def get_player_ranking_by_user_guesses(cls):
        """Get a ranking of all players sorted by their total user guess count (excluding initial guesses).
        Returns a list of tuples (player, total_user_guesses, total_guesses, total_wrong_guesses)."""
        from django.db.models import Sum
        
        # Get all players with their total guess counts
        player_stats = cls.objects.values('player_id').annotate(
            total_guesses=Sum('guess_count'),
            total_initial_guesses=Sum('initial_guesses'),
            total_wrong_guesses=Sum('wrong_guesses')
        )
        
        # Calculate user guesses and create ranking list
        ranking_data = []
        for stat in player_stats:
            try:
                player = Player.objects.get(id=stat['player_id'])
                total_guesses = stat['total_guesses'] or 0
                total_initial_guesses = stat['total_initial_guesses'] or 0
                total_wrong_guesses = stat['total_wrong_guesses'] or 0
                
                # Calculate user guesses (total - initial)
                total_user_guesses = max(0, total_guesses - total_initial_guesses)
                
                ranking_data.append({
                    'player': player,
                    'total_user_guesses': total_user_guesses,
                    'total_guesses': total_guesses,
                    'total_wrong_guesses': total_wrong_guesses,
                })
            except Player.DoesNotExist:
                # Skip if player doesn't exist
                continue
        
        # Sort by user guesses (descending)
        ranking_data.sort(key=lambda x: x['total_user_guesses'], reverse=True)
        
        # Convert to list of tuples
        ranking = []
        for data in ranking_data:
            ranking.append((
                data['player'], 
                data['total_user_guesses'], 
                data['total_guesses'], 
                data['total_wrong_guesses']
            ))
        
        return ranking


class GameCompletion(ExportModelOperationsMixin("gamecompletion"), models.Model):
    date = models.DateField()
    session_key = models.CharField(max_length=40)  # Django session key
    completed_at = models.DateTimeField(auto_now_add=True)
    correct_cells = models.IntegerField(default=0)  # Number of correctly filled cells
    final_score = models.FloatField(default=0.0)  # Final score achieved Optional additional data
    completion_streak = models.IntegerField(default=1)  # Consecutive days of completion
    perfect_streak = models.IntegerField(default=1)  # Consecutive days of perfect completion

    class Meta:
        unique_together = ["date", "session_key"]  # Each session can only complete a game once
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["final_score"]),  # Index for leaderboard queries
            models.Index(fields=["completion_streak"]),  # Index for streak queries
            models.Index(fields=["perfect_streak"]),  # Index for perfect streak queries
        ]

    def save(self, *args, **kwargs):
        """Override save to maintain streak counts."""
        if not self.pk:  # Only on creation
            # Check for previous day's completion
            prev_date = self.date - timedelta(days=1)
            try:
                prev_completion = GameCompletion.objects.get(session_key=self.session_key, date=prev_date)
                # If previous day exists, increment completion streak
                self.completion_streak = prev_completion.completion_streak + 1

                # For perfect streak, check if previous day was perfect
                if self.correct_cells == 9:
                    if prev_completion.correct_cells == 9:
                        self.perfect_streak = prev_completion.perfect_streak + 1
                    else:
                        self.perfect_streak = 1
                else:
                    self.perfect_streak = 1
            except GameCompletion.DoesNotExist:
                # No previous completion, reset streaks to 1
                self.completion_streak = 1
                self.perfect_streak = 1 if self.correct_cells == 9 else 0
        super().save(*args, **kwargs)

    @classmethod
    @trace_operation("GameCompletion.get_completion_count")
    def get_completion_count(cls, date):
        """Get the number of unique sessions that have completed this game."""
        return cls.objects.filter(date=date).count()

    @classmethod
    @trace_operation("GameCompletion.get_average_score")
    def get_average_score(cls, date):
        """Get the average score for a specific date."""
        result = cls.objects.filter(date=date).aggregate(avg_score=models.Avg("final_score"))
        return result["avg_score"] or 0

    @classmethod
    @trace_operation("GameCompletion.get_average_correct_cells")
    def get_average_correct_cells(cls, date):
        """Get the average number of correct cells for a specific date."""
        result = cls.objects.filter(date=date).aggregate(avg_cells=models.Avg("correct_cells"))
        return result["avg_cells"] or 0

    @classmethod
    @trace_operation("GameCompletion.get_perfect_games")
    def get_perfect_games(cls, date):
        """Get the number of games where all cells were correctly filled."""
        return cls.objects.filter(date=date, correct_cells=9).count()

    @classmethod
    @trace_operation("GameCompletion.get_current_streak")
    def get_current_streak(cls, session_key, current_date):
        """Get the current streak for a user.
        Returns the completion_streak for the current user."""
        try:
            # Get the user's current completion
            completion = cls.objects.get(session_key=session_key, date=current_date)
            return completion.completion_streak
        except cls.DoesNotExist:
            return 0

    @classmethod
    @trace_operation("GameCompletion.get_top_scores")
    def get_top_scores(cls, date, limit=10):
        """Get the top scores for a specific date."""
        return cls.objects.filter(date=date).order_by("-final_score")[:limit]

    @classmethod
    @trace_operation("GameCompletion.get_ranking_with_neighbors")
    def get_ranking_with_neighbors(cls, date, session_key):
        """Get a ranking that includes the current user and their 4 nearest neighbors.
        Returns a list of tuples (rank, display_name, score) where rank is 1-based."""
        # Get all completions ordered by score
        completions = cls.objects.filter(date=date).order_by("-final_score")
        total_completions = completions.count()

        if total_completions == 0:
            return []

        # Get all completions with their user data
        ranking = []
        current_user_rank = None

        for rank, completion in enumerate(completions, 1):
            try:
                display_name = UserData.get_display_name(completion.session_key)
                ranking.append((rank, display_name, completion.final_score))

                if completion.session_key == session_key:
                    current_user_rank = rank
            except Exception as e:
                logger.error(f"Error getting display name for session {completion.session_key}: {e}")
                continue

        if current_user_rank is None:
            return ranking[:5]  # Just return top 5 if current user not found

        # Calculate start and end indices to show 5 entries
        # Try to show 2 entries before and 2 entries after the current user
        start_idx = max(0, current_user_rank - 3)  # Show 2 entries before current user
        end_idx = min(len(ranking), start_idx + 5)  # Show 5 entries total

        # If we're near the end, adjust start_idx to show 5 entries
        if end_idx - start_idx < 5:
            start_idx = max(0, end_idx - 5)

        # If we're near the start, adjust end_idx to show 5 entries
        if start_idx == 0 and len(ranking) >= 5:
            end_idx = 5

        # Return the slice of ranking that includes the current user and their neighbors
        return ranking[start_idx:end_idx]

    @classmethod
    @trace_operation("GameCompletion.get_longest_streaks_ranking_with_neighbors")
    def get_longest_streaks_ranking_with_neighbors(cls, session_key):
        """Get a ranking of longest streaks that includes the current user and their 4 nearest neighbors.
        Returns a list of tuples (rank, display_name, streak) where rank is 1-based."""
        # Get all users with their longest streaks (most recent completion for each user)
        from django.db.models import Max
        
        # Get the most recent completion for each session to find their current streak
        latest_completions = cls.objects.values('session_key').annotate(
            latest_date=Max('date')
        )
        
        # Build ranking of longest streaks
        ranking = []
        current_user_rank = None
        
        for completion_data in latest_completions:
            try:
                # Get the most recent completion for this session
                latest_completion = cls.objects.get(
                    session_key=completion_data['session_key'],
                    date=completion_data['latest_date']
                )
                
                # Only include users with active streaks (streak > 0)
                if latest_completion.completion_streak > 0:
                    display_name = UserData.get_display_name(latest_completion.session_key)
                    ranking.append((latest_completion.completion_streak, display_name, latest_completion.session_key))
                    
                    if latest_completion.session_key == session_key:
                        current_user_rank = len(ranking)  # Will be updated after sorting
                        
            except Exception as e:
                logger.error(f"Error getting display name for session {completion_data['session_key']}: {e}")
                continue
        
        if not ranking:
            return []
        
        # Sort by streak length (descending) and then by display name for ties
        ranking.sort(key=lambda x: (-x[0], x[1]))
        
        # Find current user's rank after sorting
        if current_user_rank is not None:
            for rank, (streak, display_name, session) in enumerate(ranking, 1):
                if session == session_key:
                    current_user_rank = rank
                    break
        
        # Convert to (rank, display_name, streak) format
        final_ranking = []
        for rank, (streak, display_name, session) in enumerate(ranking, 1):
            final_ranking.append((rank, display_name, streak))
        
        if current_user_rank is None:
            return final_ranking[:5]  # Just return top 5 if current user not found
        
        # Calculate start and end indices to show 5 entries
        # Try to show 2 entries before and 2 entries after the current user
        start_idx = max(0, current_user_rank - 3)  # Show 2 entries before current user
        end_idx = min(len(final_ranking), start_idx + 5)  # Show 5 entries total
        
        # If we're near the end, adjust start_idx to show 5 entries
        if end_idx - start_idx < 5:
            start_idx = max(0, end_idx - 5)
        
        # If we're near the start, adjust end_idx to show 5 entries
        if start_idx == 0 and len(final_ranking) >= 5:
            end_idx = 5
        
        # Return the slice of ranking that includes the current user and their neighbors
        return final_ranking[start_idx:end_idx]

    @classmethod
    @trace_operation("GameCompletion.get_first_unplayed_game")
    def get_first_unplayed_game(cls, session_key, current_date=None):
        """Find the first unplayed game for a user, going backwards from the current date.
        Returns a tuple of (date, has_unplayed_games) where date is the first unplayed game date,
        or None if all games have been played."""
        from datetime import datetime, timedelta

        if current_date is None:
            current_date = datetime.now().date()
        elif hasattr(current_date, "date"):
            # Convert datetime to date if needed
            current_date = current_date.date()

        # Start from the current date and go backwards
        check_date = current_date
        earliest_date = datetime(2025, 4, 1).date()  # Earliest possible game date

        while check_date >= earliest_date:
            # Check if this user has completed this game
            if not cls.objects.filter(session_key=session_key, date=check_date).exists():
                return (check_date, True)
            check_date -= timedelta(days=1)

        # If we've checked all dates and found no unplayed games
        return (None, False)

    def __str__(self):
        return f"{self.date} - {self.session_key} - Score: {self.final_score} ({self.correct_cells}/9 cells)"


class GameFilterDB(ExportModelOperationsMixin("gamefilterdb"), models.Model):
    """Stores the configuration of game filters for a specific date."""

    date = models.DateField()
    filter_type = models.CharField(max_length=10)  # 'static' or 'dynamic'
    filter_class = models.CharField(max_length=50)  # Name of the filter class, e.g., 'PositionFilter', 'DynamicGameFilter'
    filter_config = models.JSONField()  # Store filter configuration
    filter_index = models.IntegerField()  # Position in the grid (0-2 for 3x3 grid)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("date", "filter_type", "filter_index")
        indexes = [
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.date} - {self.filter_type} - {self.filter_class} ({self.filter_index})"


class GameGrid(ExportModelOperationsMixin("gamegrid"), models.Model):
    """
    Central model that stores information about a specific game grid.
    Contains metadata about the grid and references to related models.
    """

    date = models.DateField(unique=True, primary_key=True)
    grid_size = models.IntegerField(default=3)  # Size of the grid (e.g., 3 for 3x3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Store the correct players count for each cell
    cell_correct_players = models.JSONField(default=dict)  # Format: {'0_0': 5, '0_1': 3, ...}

    @property
    def completion_count(self):
        """Get the completion count on the fly"""
        return GameCompletion.get_completion_count(self.date)

    @property
    def total_correct_players(self):
        """Get the total number of unique correct players across all cells"""
        total_correct_players = 0
        for _, count in self.cell_correct_players.items():
            total_correct_players += count
        return total_correct_players

    @property
    def total_guesses(self):
        """Get the total guess count on the fly by summing all GameResult.guess_count values for this date"""
        return GameResult.objects.filter(date=self.date).aggregate(total=models.Sum("guess_count"))["total"] or 0

    @property
    def total_user_guesses(self):
        """Get the total user guess count on the fly by summing all GameResult.user_guesses values for this date"""
        return GameResult.get_total_user_guesses(self.date)

    @property
    def total_wrong_guesses(self):
        """Get the total wrong guess count on the fly by summing all GameResult.wrong_guesses values for this date"""
        return GameResult.get_total_wrong_guesses(self.date)

    @property
    def average_score(self):
        """Get the average score for completions of this grid"""
        return GameCompletion.get_average_score(self.date)

    @property
    def average_correct_cells(self):
        """Get the average number of correct cells for completions of this grid"""
        return GameCompletion.get_average_correct_cells(self.date)

    def get_top_scores(self, limit=10):
        """Get the top scores for this grid"""
        return GameCompletion.get_top_scores(self.date, limit)

    def __str__(self):
        return f"Game Grid for {self.date}"


class GridMetadata(ExportModelOperationsMixin("gridmetadata"), models.Model):
    """
    Model to store additional metadata for each game grid.
    """

    date = models.DateField(unique=True, primary_key=True)
    game_title = models.CharField(max_length=40, default="")

    def __str__(self):
        return f"Grid Metadata for {self.date}"


class LastUpdated(ExportModelOperationsMixin("lastupdated"), models.Model):
    """
    Model to track when data was last updated
    """

    data_type = models.CharField(max_length=50, unique=True, help_text="Type of data that was updated (e.g., 'player_data')")
    last_updated = models.DateTimeField(auto_now=True, help_text="When this data was last updated")
    updated_by = models.CharField(max_length=100, blank=True, null=True, help_text="Who or what performed the update")
    notes = models.TextField(blank=True, null=True, help_text="Additional information about the update")

    def __str__(self):
        return f"{self.data_type} (updated: {self.last_updated})"

    @classmethod
    def update_timestamp(cls, data_type, updated_by=None, notes=None):
        """
        Update or create a timestamp entry for the given data type

        Args:
            data_type: The type of data being updated
            updated_by: Who or what performed the update
            notes: Additional notes about the update

        Returns:
            The LastUpdated instance
        """
        obj, created = cls.objects.update_or_create(data_type=data_type, defaults={"updated_by": updated_by, "notes": notes})
        return obj

    @classmethod
    def get_last_updated(cls, data_type):
        """
        Get the last update timestamp for the given data type

        Args:
            data_type: The type of data to check

        Returns:
            The timestamp or None if not found
        """
        try:
            return cls.objects.get(data_type=data_type).last_updated
        except cls.DoesNotExist:
            return None


class UserData(ExportModelOperationsMixin("userdata"), models.Model):
    """
    Model to store user-related data based on their session ID.
    This model can be extended with additional fields as needed.
    """

    session_key = models.CharField(max_length=40, primary_key=True, help_text="Django session key as primary identifier")
    display_name = models.CharField(max_length=14, help_text="Generated display name for the user")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this user data was created")
    has_made_guesses = models.BooleanField(default=False, help_text="Whether this user has made at least one guess")

    def __str__(self):
        return f"{self.display_name} ({self.session_key})"

    @classmethod
    def get_or_create_user(cls, session_key):
        """
        Get or create user data for a given session key.
        If user data already exists for this session, return it.
        Otherwise, generate new data and store it.

        Args:
            session_key: The session key to get/create user data for

        Returns:
            The UserData instance
        """
        try:
            user_data = cls.objects.get(session_key=session_key)
            return user_data
        except cls.DoesNotExist:
            # Generate new display name and create user data
            display_name = Player.generate_random_name(session_key)
            return cls.objects.create(session_key=session_key, display_name=display_name)

    @classmethod
    def get_display_name(cls, session_key):
        """
        Get the display name for a given session key.
        If no user data exists, creates it first.
        If display_name is empty or None, generates a new one.

        Args:
            session_key: The session key to get the display name for

        Returns:
            The display name string
        """
        try:
            user_data = cls.get_or_create_user(session_key)
            # Ensure display_name is not empty or None
            if not user_data.display_name:
                # Generate a new display name if the current one is empty
                user_data.display_name = Player.generate_random_name(session_key)
                user_data.save()
            return user_data.display_name
        except Exception as e:
            # Fallback: generate a display name directly if there are any issues
            logger.warning(f"Error getting display name for session {session_key}: {e}. Generating fallback name.")
            return Player.generate_random_name(session_key)


class ImpressumContent(ExportModelOperationsMixin("impressum_content"), models.Model):
    """Custom content for the Impressum modal that admins can edit"""
    title = models.CharField(max_length=200, help_text="Title for the impressum section")
    content = models.TextField(help_text="Content text for the impressum section")
    is_active = models.BooleanField(default=True, help_text="Whether this content should be displayed")
    order = models.PositiveIntegerField(default=0, help_text="Order of display in the Impressum modal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "Impressum Content"
        verbose_name_plural = "Impressum Content"

    def __str__(self):
        return self.title


class TrafficSource(ExportModelOperationsMixin("traffic_source"), models.Model):
    """
    Model to track traffic sources and referrer information for analytics.
    This helps analyze where traffic comes from (SEO, social media, referrals, etc.)
    """
    
    # Session and request information
    session_key = models.CharField(max_length=40, help_text="Django session key for user identification")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the visitor")
    
    # Traffic source classification
    source = models.CharField(max_length=50, help_text="Primary traffic source (search_engine, social_media, direct, etc.)")
    referrer = models.URLField(max_length=500, null=True, blank=True, help_text="Full referrer URL")
    referrer_domain = models.CharField(max_length=200, null=True, blank=True, help_text="Extracted referrer domain")
    
    # UTM parameters for campaign tracking
    utm_source = models.CharField(max_length=100, null=True, blank=True, help_text="UTM source parameter")
    utm_medium = models.CharField(max_length=100, null=True, blank=True, help_text="UTM medium parameter")
    utm_campaign = models.CharField(max_length=100, null=True, blank=True, help_text="UTM campaign parameter")
    utm_term = models.CharField(max_length=100, null=True, blank=True, help_text="UTM term parameter")
    utm_content = models.CharField(max_length=100, null=True, blank=True, help_text="UTM content parameter")
    
    # Request details
    path = models.CharField(max_length=200, help_text="Requested path/URL")
    query_string = models.TextField(null=True, blank=True, help_text="Full query string")
    user_agent = models.TextField(null=True, blank=True, help_text="User agent string")
    
    # Timestamps
    first_visit = models.DateTimeField(auto_now_add=True, help_text="First time this source was recorded")
    last_visit = models.DateTimeField(auto_now=True, help_text="Last time this source was recorded")
    visit_count = models.PositiveIntegerField(default=1, help_text="Number of visits from this source")
    
    # Additional metadata
    is_bot = models.BooleanField(default=False, help_text="Whether this traffic is from a bot/crawler")
    country = models.CharField(max_length=100, null=True, blank=True, help_text="Country of origin (if available)")
    
    class Meta:
        ordering = ['-last_visit']
        verbose_name = "Traffic Source"
        verbose_name_plural = "Traffic Sources"
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['referrer_domain']),
            models.Index(fields=['utm_source']),
            models.Index(fields=['utm_campaign']),
            models.Index(fields=['first_visit']),
            models.Index(fields=['last_visit']),
            models.Index(fields=['session_key']),
        ]
    
    def __str__(self):
        return f"{self.source} - {self.referrer_domain or 'Direct'} ({self.visit_count} visits)"
    
    @classmethod
    @trace_operation("TrafficSource.record_visit")
    def record_visit(cls, request, traffic_source_data):
        """
        Record a visit from a traffic source.
        Creates new record or updates existing one.
        
        Args:
            request: Django request object
            traffic_source_data: Dict containing traffic source information
            
        Returns:
            The TrafficSource instance
        """
        try:
            # Safety check: ensure we have a valid session key
            if not hasattr(request, 'session') or not request.session.session_key:
                logger.warning("Cannot record traffic source: no valid session key")
                return None
            
            # Safety check: ensure database is available
            from django.db import connection
            if not connection.is_usable():
                logger.warning("Database not available, skipping traffic source recording")
                return None
            
            # Extract referrer domain
            referrer_domain = None
            if traffic_source_data.get('referrer'):
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(traffic_source_data['referrer'])
                    referrer_domain = parsed.netloc
                except Exception:
                    pass
            
            # Safety check: ensure the model table exists
            try:
                # Check if we already have a record for this session and source
                existing = cls.objects.filter(
                    session_key=request.session.session_key,
                    source=traffic_source_data['source'],
                    referrer_domain=referrer_domain
                ).first()
                
                if existing:
                    # Update existing record
                    existing.visit_count += 1
                    existing.last_visit = timezone.now()
                    existing.save()
                    return existing
                else:
                    # Create new record
                    return cls.objects.create(
                        session_key=request.session.session_key,
                        ip_address=cls._get_client_ip(request),
                        source=traffic_source_data['source'],
                        referrer=traffic_source_data.get('referrer'),
                        referrer_domain=referrer_domain,
                        utm_source=traffic_source_data.get('utm_source'),
                        utm_medium=traffic_source_data.get('utm_medium'),
                        utm_campaign=traffic_source_data.get('utm_campaign'),
                        utm_term=traffic_source_data.get('utm_term'),
                        utm_content=traffic_source_data.get('utm_content'),
                        path=traffic_source_data.get('path'),
                        query_string=traffic_source_data.get('query_string'),
                        user_agent=traffic_source_data.get('user_agent'),
                        is_bot=traffic_source_data['source'] == 'bot'
                    )
            except Exception as table_error:
                logger.warning(f"TrafficSource table not available: {table_error}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording traffic source visit: {e}")
            return None
    
    @classmethod
    def _get_client_ip(cls, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @classmethod
    def get_source_summary(cls, days=30):
        """
        Get summary statistics for traffic sources over the specified period.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict with traffic source statistics
        """
        from django.utils import timezone
        from django.db.models import Count, Sum
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get source breakdown
        source_stats = cls.objects.filter(
            first_visit__gte=cutoff_date
        ).values('source').annotate(
            total_visits=Sum('visit_count'),
            unique_sessions=Count('session_key', distinct=True)
        ).order_by('-total_visits')
        
        # Get referrer domain breakdown
        referrer_stats = cls.objects.filter(
            first_visit__gte=cutoff_date,
            referrer_domain__isnull=False
        ).values('referrer_domain').annotate(
            total_visits=Sum('visit_count'),
            unique_sessions=Count('session_key', distinct=True)
        ).order_by('-total_visits')[:20]  # Top 20 referrers
        
        # Get UTM campaign breakdown
        utm_stats = cls.objects.filter(
            first_visit__gte=cutoff_date,
            utm_campaign__isnull=False
        ).values('utm_campaign').annotate(
            total_visits=Sum('visit_count'),
            unique_sessions=Count('session_key', distinct=True)
        ).order_by('-total_visits')
        
        return {
            'source_breakdown': list(source_stats),
            'top_referrers': list(referrer_stats),
            'utm_campaigns': list(utm_stats),
            'period_days': days
        }
