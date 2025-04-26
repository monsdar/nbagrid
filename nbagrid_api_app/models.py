from django.db import models

from nba_api.stats.endpoints import commonplayerinfo, playercareerstats

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
    
    def __str__(self):
        return self.name
    def has_played_for_team(self, abbr):
        return self.teams.filter(abbr=abbr).exists()
    
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
    def initialize_scores_from_recent_games(cls, date, cell_key, num_games=5, game_factor=5):
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
            
        # For each game date, get the top 10 most picked players
        top_players = {}
        for game_date in recent_dates:
            # Get top 10 players for this game date (across all cells)
            top_players_for_date = cls.objects.filter(date=game_date)\
                .values('player')\
                .annotate(total_guesses=models.Sum('guess_count'))\
                .order_by('-total_guesses')[:10]
            
            # Increment count for each top player
            for player_data in top_players_for_date:
                player_id = player_data['player']
                top_players[player_id] = top_players.get(player_id, 0) + 1
        
        # Create or update GameResult entries for these players
        for player_id, count in top_players.items():
            cls.objects.update_or_create(
                date=date,
                cell_key=cell_key,
                player_id=player_id,
                defaults={'guess_count': count*game_factor}
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
    