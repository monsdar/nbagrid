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
    