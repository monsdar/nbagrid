from django.db import models

from nba_api.stats.endpoints import commonplayerinfo, playercareerstats, playerawards

import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Player(models.Model):
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
                if high['STAT'] == 'PTS': self.career_high_pts = high['STAT_VALUE']
                elif high['STAT'] == 'AST': self.career_high_ast = high['STAT_VALUE']
                elif high['STAT'] == 'REB': self.career_high_reb = high['STAT_VALUE']
                elif high['STAT'] == 'STL': self.career_high_stl = high['STAT_VALUE']
                elif high['STAT'] == 'BLK': self.career_high_blk = high['STAT_VALUE']
                elif high['STAT'] == 'TOV': self.career_high_to = high['STAT_VALUE']
                elif high['STAT'] == 'FGM': self.career_high_fg = high['STAT_VALUE']
                elif high['STAT'] == 'FG3M': self.career_high_3p = high['STAT_VALUE']
                elif high['STAT'] == 'FTA': self.career_high_ft = high['STAT_VALUE']
        else:
            logger.info(f"Player {self.name} has no recorded career highs...")
            
        self.save()
        
    def convert_lbs_to_kg(self, weight_lbs: int) -> int:
        return weight_lbs * 0.453592
    
    def convert_height_to_cm(self, height_str: str) -> int:
        feet = int(height_str.split('-')[0])
        inches = int(height_str.split('-')[1])
        return (feet * 12 + inches) * 2.54
    
class Team(models.Model):
    stats_id = models.IntegerField()
    name = models.CharField(max_length=200)
    abbr = models.CharField(max_length=3)
    
    def __str__(self):
        return f"{self.abbr} {self.name}" if self.abbr else self.name
    
class GameResult(models.Model):
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
    
class GameCompletion(models.Model):
    date = models.DateField()
    session_key = models.CharField(max_length=40)  # Django session key
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['date', 'session_key']  # Each session can only complete a game once

    @classmethod
    def get_completion_count(cls, date):
        """Get the number of unique sessions that have completed this game."""
        return cls.objects.filter(date=date).count()

class GameFilterDB(models.Model):
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
    