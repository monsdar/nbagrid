from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

from nba_api.stats.endpoints import commonplayerinfo, playercareerstats, playerawards

import logging
from datetime import timedelta


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Player(ExportModelOperationsMixin('player'), models.Model):
    stats_id = models.IntegerField()
    
    # Player data
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, default="")
    teams = models.ManyToManyField('Team')
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
    is_award_mip                  = models.BooleanField(default=False)    # NBA Most Improved Player
    is_award_champ                = models.BooleanField(default=False)    # NBA Champion
    is_award_dpoy                 = models.BooleanField(default=False)    # NBA Defensive Player of the Year
    is_award_all_nba_first        = models.BooleanField(default=False)    # All-NBA
    is_award_all_nba_second       = models.BooleanField(default=False)    # All-NBA
    is_award_all_nba_third        = models.BooleanField(default=False)    # All-NBA
    is_award_all_rookie           = models.BooleanField(default=False)    # All-Rookie Team
    is_award_all_defensive        = models.BooleanField(default=False)    # All-Defensive Team
    is_award_all_star             = models.BooleanField(default=False)    # NBA All-Star
    is_award_all_star_mvp         = models.BooleanField(default=False)    # NBA All-Star Most Valuable Player
    is_award_rookie_of_the_year   = models.BooleanField(default=False)    # NBA Rookie of the Year
    is_award_mvp                  = models.BooleanField(default=False)    # NBA Most Valuable Player
    is_award_finals_mvp           = models.BooleanField(default=False)    # NBA Finals Most Valuable Player
    is_award_olympic_gold_medal   = models.BooleanField(default=False)    # Olympic Gold Medal
    is_award_olympic_silver_medal = models.BooleanField(default=False)    # Olympic Silver Medal
    is_award_olympic_bronze_medal = models.BooleanField(default=False)    # Olympic Bronze Medal
    
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
        random.seed(seed_hash)
        
        # Get all unique first and last names from players
        all_names = cls.objects.values_list('name', flat=True)
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
            first = random.choice(list(first_names))
            last = random.choice(list(last_names))
            combined = f"{first} {last}"
            
            if len(combined) <= 14:
                return combined
        
        # If we couldn't find a short enough combination, truncate the last one
        return combined[:14]

    def has_played_for_team(self, abbr):
        return self.teams.filter(abbr=abbr).exists()
    
    def update_player_awards_from_nba_stats(self):
        awards = playerawards.PlayerAwards(player_id=self.stats_id).get_normalized_dict()
        for award in awards['PlayerAwards']:
            award_name = award['DESCRIPTION']
            if award_name == 'NBA Most Improved Player':
                self.is_award_mip = True
            elif award_name == 'NBA Champion':
                self.is_award_champ = True
            elif award_name == 'NBA Defensive Player of the Year':
                self.is_award_dpoy = True
            elif award_name == 'All-NBA':
                if award['ALL_NBA_TEAM_NUMBER'] == '1':
                    self.is_award_all_nba_first = True
                elif award['ALL_NBA_TEAM_NUMBER'] == '2':
                    self.is_award_all_nba_second = True
                elif award['ALL_NBA_TEAM_NUMBER'] == '3':
                    self.is_award_all_nba_third = True
            elif award_name == 'All-Rookie Team':
                self.is_award_all_rookie = True
            elif award_name == 'All-Defensive Team':
                self.is_award_all_defensive = True
            elif award_name == 'NBA All-Star':
                self.is_award_all_star = True
            elif award_name == 'NBA All-Star Most Valuable Player':
                self.is_award_all_star_mvp = True
            elif award_name == 'NBA Rookie of the Year':
                self.is_award_rookie_of_the_year = True
            elif award_name == 'NBA Most Valuable Player':
                self.is_award_mvp = True
            elif award_name == 'NBA Finals Most Valuable Player':
                self.is_award_finals_mvp = True
            elif award_name == 'Olympic Gold Medal':
                self.is_award_olympic_gold_medal = True
            elif award_name == 'Olympic Silver Medal':
                self.is_award_olympic_silver_medal = True
            elif award_name == 'Olympic Bronze Medal':
                self.is_award_olympic_bronze_medal = True
        self.save()
    
    def update_player_data_from_nba_stats(self):
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=self.stats_id).get_normalized_dict()
        draft_year = player_info['CommonPlayerInfo'][0]['DRAFT_YEAR']
        draft_year = 0 if (draft_year == 'Undrafted') else int(draft_year)
        draft_round = player_info['CommonPlayerInfo'][0]['DRAFT_ROUND']
        draft_round = 0 if ((not draft_round) or (draft_round == 'Undrafted')) else int(draft_round)
        draft_number = player_info['CommonPlayerInfo'][0]['DRAFT_NUMBER']
        draft_number = 0 if ((not draft_number) or draft_number == 'Undrafted') else int(draft_number)
        self.draft_year = draft_year
        self.draft_round = draft_round
        self.draft_number = draft_number
        self.is_undrafted = True if (draft_round + draft_number == 0) else False
        self.is_greatest_75 = True if (player_info['CommonPlayerInfo'][0]['GREATEST_75_FLAG'] == 'Y') else False
        self.num_seasons = player_info['CommonPlayerInfo'][0]['SEASON_EXP']
        weight = player_info['CommonPlayerInfo'][0]['WEIGHT']
        weight = 0 if not weight else int(weight) # some players have '' as their weight
        if weight == 0:
            logger.info(f"Player {self.name} has no weight!!")
        self.weight_kg = self.convert_lbs_to_kg(weight)
        self.height_cm = self.convert_height_to_cm(player_info['CommonPlayerInfo'][0]['HEIGHT'])
        self.country = player_info['CommonPlayerInfo'][0]['COUNTRY']
        self.position = player_info['CommonPlayerInfo'][0]['POSITION']
        self.save()
    
    def update_player_stats_from_nba_stats(self):
        player_stats = playercareerstats.PlayerCareerStats(player_id=self.stats_id, per_mode36='PerGame', league_id_nullable='00').get_normalized_dict()
        for season in player_stats['SeasonTotalsRegularSeason']:
            season_team_id = season['TEAM_ID']
            if Team.objects.filter(stats_id=season_team_id).exists():
                self.teams.add(Team.objects.get(stats_id=season_team_id))
        
        if player_stats['CareerTotalsRegularSeason']:
            career_totals = player_stats['CareerTotalsRegularSeason'][0]
            self.career_gp = career_totals['GP']
            self.career_gs = career_totals['GS']
            self.career_min = career_totals['MIN']
            self.career_apg = career_totals['AST']
            self.career_ppg = career_totals['PTS']
            self.career_rpg = career_totals['REB']
            self.career_bpg = career_totals['BLK']
            self.career_spg = career_totals['STL']
            self.career_tpg = career_totals['TOV']
            self.career_fgp = career_totals['FG_PCT']
            self.career_3gp = career_totals['FG3_PCT']
            self.career_ftp = career_totals['FT_PCT']
            self.career_fga = career_totals['FGA']
            self.career_3pa = career_totals['FG3A']
            self.career_fta = career_totals['FTA']
        else:
            logger.info(f"Player {self.name} has no stats, probably a GLeague player...")
        
        if 'CareerHighs' in player_stats:
            career_highs = player_stats['CareerHighs']
            for high in career_highs:
                if not 'STAT_VALUE' in high:
                    logger.info(f"Player {self.name} has invalid career high record, skipping...")
                    continue
                stat_value = high['STAT_VALUE']
                if high['STAT'] == 'PTS' and stat_value > self.career_high_pts: self.career_high_pts = stat_value
                elif high['STAT'] == 'AST' and stat_value > self.career_high_ast: self.career_high_ast = stat_value
                elif high['STAT'] == 'REB' and stat_value > self.career_high_reb: self.career_high_reb = stat_value
                elif high['STAT'] == 'STL' and stat_value > self.career_high_stl: self.career_high_stl = stat_value
                elif high['STAT'] == 'BLK' and stat_value > self.career_high_blk: self.career_high_blk = stat_value
                elif high['STAT'] == 'TOV' and stat_value > self.career_high_to: self.career_high_to = stat_value
                elif high['STAT'] == 'FGM' and stat_value > self.career_high_fg: self.career_high_fg = stat_value
                elif high['STAT'] == 'FG3M' and stat_value > self.career_high_3p: self.career_high_3p = stat_value
                elif high['STAT'] == 'FTA' and stat_value > self.career_high_ft: self.career_high_ft = stat_value
        else:
            logger.info(f"Player {self.name} has no recorded career highs...")
            
        self.save()
        
    def convert_lbs_to_kg(self, weight_lbs: int) -> int:
        return weight_lbs * 0.453592
    
    def convert_height_to_cm(self, height_str: str) -> int:
        feet = int(height_str.split('-')[0])
        inches = int(height_str.split('-')[1])
        return (feet * 12 + inches) * 2.54
    
class Team(ExportModelOperationsMixin('team'), models.Model):
    stats_id = models.IntegerField()
    name = models.CharField(max_length=200)
    abbr = models.CharField(max_length=3)
    
    def __str__(self):
        return f"{self.abbr} {self.name}" if self.abbr else self.name
    
class GameResult(ExportModelOperationsMixin('gameresult'), models.Model):
    date = models.DateField()
    cell_key = models.CharField(max_length=10)  # e.g., "0_1" for row 0, col 1
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    guess_count = models.IntegerField(default=1)  # Number of times this player was correctly guessed for this cell

    class Meta:
        unique_together = ['date', 'cell_key', 'player']  # Ensure we can track multiple correct players per cell
        
    @classmethod
    def get_cell_stats(cls, date, cell_key):
        """Get all correct players and their guess counts for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key).select_related('player')

    @classmethod
    def get_most_common_players(cls, date, cell_key, limit=5):
        """Get the most commonly guessed players for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key)\
            .select_related('player')\
            .order_by('-guess_count')[:limit]

    @classmethod
    def get_rarest_players(cls, date, cell_key, limit=5):
        """Get the rarest correct guesses for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key)\
            .select_related('player')\
            .order_by('guess_count')[:limit]

    @classmethod
    def get_total_guesses(cls, date):
        """Get the total number of correct guesses for a specific date."""
        return cls.objects.filter(date=date).aggregate(total=models.Sum('guess_count'))['total'] or 0

    @classmethod
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
            total_guesses = cls.objects.filter(date=date, cell_key=cell_key).aggregate(
                total=models.Sum('guess_count')
            )['total'] or 1
            return 1 - (result.guess_count / total_guesses)
        except cls.DoesNotExist:
            return 1.0  # Player hasn't been guessed yet for this cell on this date

    @classmethod
    def initialize_scores_from_recent_games(cls, date, cell_key, num_games=5, game_factor=5, filters=[]):
        """Initialize GameResult entries for players based on their appearances in recent games.
        For each of the last 5 games, we check the top 10 most picked players (across all cells).
        If a player is in the top 10 for a game, their count increases by 1.
        The maximum count a player can have is 5 (if they were in top 10 for all 5 games).
        
        The game_factor is a multiplier for the number of appearances.
        For example, if a player appears in the top 10 for 3 games, they will have an
        initial score of 3 * game_factor. This is to account for the fact that players with 5 appearances
        should have a "Common" appearance in comparison to players with 1 appearance. Due to the
        number of overall players this won't happen without that factor.
        
        Args:
            date: The date to initialize scores for
            cell_key: The cell key to initialize scores for
            num_games: Number of recent games to look back at
            game_factor: Factor to multiply the number of appearances by
        """
        # Get the date range for recent games
        recent_dates = cls.objects.filter(date__lt=date)\
            .order_by('-date')\
            .values_list('date', flat=True)\
            .distinct()[:num_games]
        
        if not recent_dates:
            return
            
        logger.debug(f"Initializing scores for date {date}, cell {cell_key}")
        logger.debug(f"Found {len(recent_dates)} recent dates: {recent_dates}")
            
        # For each game date, get the top 10 most picked players
        top_players = {}
        for game_date in recent_dates:
            # Get top 10 players for this game date (across all cells)
            top_players_for_date = cls.objects.filter(date=game_date)\
                .select_related('player')\
                .values('player', 'player__stats_id')\
                .annotate(total_guesses=models.Sum('guess_count'))\
                .order_by('-total_guesses')[:10]
            
            logger.debug(f"For date {game_date}, found {len(top_players_for_date)} top players")
            
            # Increment count for each top player
            for player_data in top_players_for_date:
                player_id = player_data['player__stats_id']
                player_key = player_data['player']
                
                # check if player matches any of the filters if any are given
                if filters:
                    player = Player.objects.filter(stats_id=player_id)
                    logger.debug(f"Checking player {player_id} against filters...")
                    for f in filters:
                        logger.debug(f"...applying filter '{f.get_desc()}' to player {player_id}")
                        player = f.apply_filter(player)
                    if not player:
                        logger.debug(f"Player {player_id} does not match the filters, skipping")
                        continue
                    else:
                        logger.debug(f"Player {player_id} matches the filters, adding to initial players for that cell")
                    
                # add the player to the top players
                if player_key not in top_players:
                    top_players[player_key] = 0
                top_players[player_key] += 1
                logger.debug(f"Player {player_id} now has {top_players[player_key]} appearances")
        
        logger.debug(f"Final player appearances: {top_players}")
        
        # Create or update GameResult entries for these players
        for player_key, count in top_players.items():
            final_count = count * game_factor
            logger.debug(f"Setting player {player_key} count to {final_count} ({count} appearances * {game_factor})")
            cls.objects.update_or_create(
                date=date,
                cell_key=cell_key,
                player_id=player_key,
                defaults={'guess_count': final_count}
            )

    def __str__(self):
        return f"{self.date} - {self.cell_key} - {self.player.name} ({self.guess_count} guesses)"
    
class GameCompletion(ExportModelOperationsMixin('gamecompletion'), models.Model):
    date = models.DateField()
    session_key = models.CharField(max_length=40)  # Django session key
    completed_at = models.DateTimeField(auto_now_add=True)
    correct_cells = models.IntegerField(default=0)  # Number of correctly filled cells
    final_score = models.FloatField(default=0.0)    # Final score achieved Optional additional data
    completion_streak = models.IntegerField(default=1)  # Consecutive days of completion
    perfect_streak = models.IntegerField(default=1)  # Consecutive days of perfect completion

    class Meta:
        unique_together = ['date', 'session_key']  # Each session can only complete a game once
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['final_score']),  # Index for leaderboard queries
            models.Index(fields=['completion_streak']),  # Index for streak queries
            models.Index(fields=['perfect_streak']),  # Index for perfect streak queries
        ]

    def save(self, *args, **kwargs):
        """Override save to maintain streak counts."""
        if not self.pk:  # Only on creation
            # Check for previous day's completion
            prev_date = self.date - timedelta(days=1)
            try:
                prev_completion = GameCompletion.objects.get(
                    session_key=self.session_key,
                    date=prev_date
                )
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
    def get_completion_count(cls, date):
        """Get the number of unique sessions that have completed this game."""
        return cls.objects.filter(date=date).count()
    
    @classmethod
    def get_average_score(cls, date):
        """Get the average score for a specific date."""
        result = cls.objects.filter(date=date).aggregate(avg_score=models.Avg('final_score'))
        return result['avg_score'] or 0
    
    @classmethod
    def get_average_correct_cells(cls, date):
        """Get the average number of correct cells for a specific date."""
        result = cls.objects.filter(date=date).aggregate(avg_cells=models.Avg('correct_cells'))
        return result['avg_cells'] or 0
    
    @classmethod
    def get_perfect_games(cls, date):
        """Get the number of games where all cells were correctly filled."""
        return cls.objects.filter(date=date, correct_cells=9).count()
    
    @classmethod
    def get_current_streak(cls, session_key, current_date):
        """Get the current streak for a user.
        Returns a tuple of (completion_streak, streak_rank, total_completions) where streak_rank is the user's position
        among all users' active streaks."""
        try:
            # Get the user's current completion
            completion = cls.objects.get(
                session_key=session_key,
                date=current_date
            )
            streak = completion.completion_streak
            
            # Get all completions for this date that are part of an active streak
            # A completion is part of an active streak if it's the most recent completion for that session
            active_completions = []
            all_sessions = cls.objects.values('session_key').distinct()
            
            for session in all_sessions:
                try:
                    # Get the most recent completion for this session
                    latest_completion = cls.objects.filter(
                        session_key=session['session_key'],
                        date=current_date
                    ).first()
                    
                    # Only include if it's from today and has a streak
                    if latest_completion and latest_completion.completion_streak > 0:
                        active_completions.append(latest_completion.completion_streak)
                except cls.DoesNotExist:
                    continue
            
            total_completions = len(active_completions)
            
            # If there's only one player with a streak, they're rank 1 of 1
            if total_completions == 1:
                return (streak, 1, 1)
            
            # Sort streaks in descending order
            active_completions.sort(reverse=True)
            
            # Find the rank of the current user's streak
            streak_rank = 1
            for rank in active_completions:
                if rank < streak:
                    break
                if rank == streak:
                    return (streak, streak_rank, total_completions)
                streak_rank += 1
                
            return (streak, streak_rank, total_completions)
            
        except cls.DoesNotExist:
            return (0, 0, 0)
    
    @classmethod
    def get_top_scores(cls, date, limit=10):
        """Get the top scores for a specific date."""
        return cls.objects.filter(date=date).order_by('-final_score')[:limit]
    
    @classmethod
    def get_ranking_with_neighbors(cls, date, session_key):
        """Get a ranking that includes the current user and their 4 nearest neighbors.
        Returns a list of tuples (rank, display_name, score) where rank is 1-based."""
        # Get all completions ordered by score
        completions = cls.objects.filter(date=date).order_by('-final_score')
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
    
    def __str__(self):
        return f"{self.date} - {self.session_key} - Score: {self.final_score} ({self.correct_cells}/9 cells)"

class GameFilterDB(ExportModelOperationsMixin('gamefilterdb'), models.Model):
    """Stores the configuration of game filters for a specific date."""
    date = models.DateField()
    filter_type = models.CharField(max_length=10)  # 'static' or 'dynamic'
    filter_class = models.CharField(max_length=50)  # Name of the filter class, e.g., 'PositionFilter', 'DynamicGameFilter'
    filter_config = models.JSONField()  # Store filter configuration
    filter_index = models.IntegerField()  # Position in the grid (0-2 for 3x3 grid)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('date', 'filter_type', 'filter_index')
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.filter_type} - {self.filter_class} ({self.filter_index})"

class GameGrid(ExportModelOperationsMixin('gamegrid'), models.Model):
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
        return GameResult.objects.filter(date=self.date).aggregate(
            total=models.Sum('guess_count')
        )['total'] or 0
    
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

class LastUpdated(ExportModelOperationsMixin('lastupdated'),    models.Model):
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
        obj, created = cls.objects.update_or_create(
            data_type=data_type,
            defaults={
                'updated_by': updated_by,
                'notes': notes
            }
        )
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

class UserData(ExportModelOperationsMixin('userdata'), models.Model):
    """
    Model to store user-related data based on their session ID.
    This model can be extended with additional fields as needed.
    """
    session_key = models.CharField(max_length=40, primary_key=True, help_text="Django session key as primary identifier")
    display_name = models.CharField(max_length=14, help_text="Generated display name for the user")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this user data was created")
    last_active = models.DateTimeField(auto_now=True, help_text="When this user was last active")

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
            # Update last_active timestamp
            user_data.save()  # This will trigger auto_now=True for last_active
            return user_data
        except cls.DoesNotExist:
            # Generate new display name and create user data
            display_name = Player.generate_random_name(session_key)
            return cls.objects.create(
                session_key=session_key,
                display_name=display_name
            )

    @classmethod
    def get_display_name(cls, session_key):
        """
        Get the display name for a given session key.
        If no user data exists, creates it first.
        
        Args:
            session_key: The session key to get the display name for
            
        Returns:
            The display name string
        """
        return cls.get_or_create_user(session_key).display_name
    