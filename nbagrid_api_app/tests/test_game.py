from django.test import TestCase
from django.db.models import F

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import Player, Team, GameResult, GameFilterDB
from nbagrid_api_app.GameFilter import create_filter_from_db
from nba_api.stats.endpoints import commonplayerinfo, playercareerstats, playerawards
from datetime import date, timedelta

import random

def populate_teams(num_teams:int=30):
    random.seed(0)
    for index in range(num_teams):
        team = Team.objects.create(stats_id=index, name=f"Team {index}", abbr=f"ABBR{index}")
        
def populate_players(num_players:int=100):
    random.seed(0)
    for index in range(num_players):
        player = Player.objects.create(stats_id=index, name=f"Player {index}")
        player.teams.set(random.sample(list(Team.objects.all()), random.randint(1,5)))
        player.career_gp = random.gauss(400, 300)
        player.num_seasons = random.gauss(10, 5)
        player.height_cm = random.gauss(200, 10)
        player.weight_kg = random.gauss(90, 30)
        player.career_ppg = random.gauss(15, 10)
        player.career_apg = random.gauss(7, 5)
        player.career_rpg = random.gauss(7, 5)
        player.career_bpg = random.gauss(1, 0.5)
        player.career_spg = random.gauss(2, 1)
        player.career_tpg = random.gauss(3, 1)
        player.career_fgp = random.gauss(0.5, 0.1)
        player.career_3gp = random.gauss(0.2, 0.1)
        player.career_ftp = random.gauss(0.8, 0.1)
        player.career_fga = random.gauss(10, 5)
        player.career_3pa = random.gauss(5, 3)
        player.career_fta = random.gauss(5, 3)
        player.career_high_pts = random.gauss(30, 15)
        player.career_high_ast = random.gauss(10, 5)
        player.career_high_reb = random.gauss(15, 10)
        player.career_high_stl = random.gauss(3, 1)
        player.career_high_blk = random.gauss(3, 2)
        player.career_high_to = random.gauss(5, 2)
        player.career_high_fg = random.gauss(5, 3)
        player.career_high_3p = random.gauss(5, 2)
        player.career_high_ft = random.gauss(5, 2)
        player.draft_year = random.gauss(2015, 10)
        player.draft_round = random.randint(1,2)
        player.draft_number = random.randint(1,60)
        player.position = random.choice(['Guard', 'Forward', 'Center'])
        player.is_undrafted = random.choices(population=[True, False],
                                             weights=[0.25, 0.75],
                                             k=1)[0]
        player.country = random.choices(population=['USA', 'Germany', 'Brazil', 'Serbia', 'United Kingdom', 'Puerto Rico', 'Ghana'],
                                        weights=   [ 0.7,      0.05,     0.05,     0.05,             0.05,          0.05,    0.05],
                                        k=1)[0]
        player.is_greatest_75 = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]
        player.is_award_all_nba_first = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]
        player.is_award_all_nba_second = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_all_nba_third = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]
        player.is_award_all_rookie = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_all_defensive = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_all_star = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_all_star_mvp = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_rookie_of_the_year = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]    
        player.is_award_mvp = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_finals_mvp = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_olympic_gold_medal = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_olympic_silver_medal = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]  
        player.is_award_olympic_bronze_medal = random.choices(population=[True, False],
                                               weights=   [ 0.1, 0.9],
                                               k=1)[0]
        player.save()
        
class GameBuilderTest(TestCase):
    def test_build_filter_pairs(self):
        # Clean up any existing records
        GameFilterDB.objects.all().delete()
        GameResult.objects.all().delete()
        
        populate_teams(30)
        populate_players(600)
        
        for index in range(10):
            builder = GameBuilder(index)
            (static_filters, dynamic_filters) = builder.get_tuned_filters(date.today())
            self.assertEqual(len(static_filters), 3)
            self.assertEqual(len(dynamic_filters), 3)
        
class PlayerTest(TestCase):
    def test_has_played_for_team(self):
        player = Player.objects.create(stats_id=1, name='Lebron James')
        team = Team.objects.create(stats_id=1, name='Cavaliers', abbr='CLE')
        player.teams.add(team)
        self.assertTrue(player.has_played_for_team('CLE'))
        
    def test_has_not_played_for_team(self):
        player = Player.objects.create(stats_id=1, name='Lebron James')
        self.assertFalse(player.has_played_for_team('CLE'))
        
    def test_load_player_data(self):
        #player = Player.objects.create(stats_id=202681, name='Kyrie Irving')
        player = Player.objects.create(stats_id=2544, name='LeBron James')
        #player = Player.objects.create(stats_id=201142, name='Kevin Durant')
        #player = Player.objects.create(stats_id=201566, name='Russell Westbrook')
        #player = Player.objects.create(stats_id=203999, name='Nikola Jokic')
        #player = Player.objects.create(stats_id=203507, name='Giannis Antetokounmpo')
        #player = Player.objects.create(stats_id=1629029, name='Luka Doncic')
        
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player.stats_id).get_normalized_dict()
        player.draft_year = player_info['CommonPlayerInfo'][0]['DRAFT_YEAR']
        player.draft_round = player_info['CommonPlayerInfo'][0]['DRAFT_ROUND']
        player.draft_number = player_info['CommonPlayerInfo'][0]['DRAFT_NUMBER']
        player.is_greatest_75 = True if (player_info['CommonPlayerInfo'][0]['GREATEST_75_FLAG'] == 'Y') else False
        player.num_seasons = player_info['CommonPlayerInfo'][0]['SEASON_EXP']
        player.country = player_info['CommonPlayerInfo'][0]['COUNTRY']
        player.position = player_info['CommonPlayerInfo'][0]['POSITION']
        
        player_stats = playercareerstats.PlayerCareerStats(player_id=player.stats_id, per_mode36='PerGame', league_id_nullable='00').get_normalized_dict()
        
        career_totals = player_stats['CareerTotalsRegularSeason'][0]
        player.career_gp = career_totals['GP']
        player.career_gs = career_totals['GS']
        player.career_min = career_totals['MIN']
        player.career_apg = career_totals['AST']
        player.career_ppg = career_totals['PTS']
        player.career_rpg = career_totals['REB']
        player.career_bpg = career_totals['BLK']
        player.career_spg = career_totals['STL']
        player.career_tpg = career_totals['TOV']
        player.career_fgp = career_totals['FG_PCT']
        player.career_3gp = career_totals['FG3_PCT']
        player.career_ftp = career_totals['FT_PCT']
        player.career_fga = career_totals['FGA']
        player.career_3pa = career_totals['FG3A']
        player.career_fta = career_totals['FTA']
        
        career_highs = player_stats['CareerHighs']
        for high in career_highs:
            if high['STAT'] == 'PTS': player.career_high_pts = high['STAT_VALUE']
            elif high['STAT'] == 'AST': player.career_high_ast = high['STAT_VALUE']
            elif high['STAT'] == 'REB': player.career_high_reb = high['STAT_VALUE']
            elif high['STAT'] == 'STL': player.career_high_stl = high['STAT_VALUE']
            elif high['STAT'] == 'BLK': player.career_high_blk = high['STAT_VALUE']
            elif high['STAT'] == 'TOV': player.career_high_to = high['STAT_VALUE']
            elif high['STAT'] == 'FGM': player.career_high_fg = high['STAT_VALUE']
            elif high['STAT'] == 'FG3M': player.career_high_3p = high['STAT_VALUE']
            elif high['STAT'] == 'FTA': player.career_high_ft = high['STAT_VALUE']
            
            
        player_ids = [202681, 2544, 201142, 201566, 203999, 203507, 1629029]
        all_awards = set()
        for player_id in player_ids:
            awards = playerawards.PlayerAwards(player_id=player_id).get_normalized_dict()
            for award in awards['PlayerAwards']:
                all_awards.add(award['DESCRIPTION'])
        #for award in all_awards:
        #    print(award)
          
        # Some of the Values:  
        # NBA Most Improved Player
        # NBA In-Season Tournament Most Valuable Player
        # NBA In-Season Tournament All-Tournament
        # NBA Champion
        # NBA Defensive Player of the Year
        # All-NBA
        # All-Rookie Team
        # All-Defensive Team
        # NBA All-Star
        # NBA All-Star Most Valuable Player
        # NBA Rookie of the Year
        # NBA Player of the Week
        # NBA Rookie of the Month
        # NBA Most Valuable Player
        # NBA Sporting News Most Valuable Player of the Year
        # NBA Sporting News Rookie of the Year
        # NBA Player of the Month
        # NBA Finals Most Valuable Player
        # Olympic Gold Medal
        # Olympic Silver Medal
        # Olympic Bronze Medal
                        
        player.save()

class GameResultTests(TestCase):
    def setUp(self):
        # Clean up any existing records
        GameResult.objects.all().delete()
        
        # Create test teams
        self.team1 = Team.objects.create(stats_id=1, name="Team 1", abbr="T1")
        self.team2 = Team.objects.create(stats_id=2, name="Team 2", abbr="T2")

        # Create test players
        self.player1 = Player.objects.create(stats_id=1, name="Player 1")
        self.player1.teams.add(self.team1)
        self.player2 = Player.objects.create(stats_id=2, name="Player 2")
        self.player2.teams.add(self.team2)
        self.player3 = Player.objects.create(stats_id=3, name="Player 3")
        self.player3.teams.add(self.team1)

        # Set test date
        self.test_date = date.today()
        self.cell_key = "0_1"

    def test_get_cell_stats(self):
        # Create some game results
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player1, guess_count=5)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player2, guess_count=3)

        stats = GameResult.get_cell_stats(self.test_date, self.cell_key)
        self.assertEqual(stats.count(), 2)
        self.assertEqual(stats[0].player.name, "Player 1")
        self.assertEqual(stats[1].player.name, "Player 2")

    def test_get_most_common_players(self):
        # Create game results with different guess counts
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player1, guess_count=5)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player2, guess_count=3)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player3, guess_count=7)

        common_players = GameResult.get_most_common_players(self.test_date, self.cell_key)
        self.assertEqual(common_players[0].player.name, "Player 3")  # Most guessed
        self.assertEqual(common_players[1].player.name, "Player 1")
        self.assertEqual(common_players[2].player.name, "Player 2")

    def test_get_rarest_players(self):
        # Create game results with different guess counts
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player1, guess_count=5)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player2, guess_count=3)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player3, guess_count=7)

        rare_players = GameResult.get_rarest_players(self.test_date, self.cell_key)
        self.assertEqual(rare_players[0].player.name, "Player 2")  # Least guessed
        self.assertEqual(rare_players[1].player.name, "Player 1")
        self.assertEqual(rare_players[2].player.name, "Player 3")

    def test_get_player_rarity_score(self):
        # Create game results
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player1, guess_count=5)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player2, guess_count=3)
        GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player3, guess_count=7)

        # Test rarity scores
        score1 = GameResult.get_player_rarity_score(self.test_date, self.cell_key, self.player1)
        score2 = GameResult.get_player_rarity_score(self.test_date, self.cell_key, self.player2)
        score3 = GameResult.get_player_rarity_score(self.test_date, self.cell_key, self.player3)

        # Player 2 should have the highest rarity score (least guessed)
        self.assertGreater(score2, score1)
        self.assertGreater(score2, score3)
        # Player 3 should have the lowest rarity score (most guessed)
        self.assertLess(score3, score1)
        self.assertLess(score3, score2)

    def test_get_player_rarity_score_new_player(self):
        # Test rarity score for a player that hasn't been guessed yet
        score = GameResult.get_player_rarity_score(self.test_date, self.cell_key, self.player1)
        self.assertEqual(score, 1.0)  # Should be 1.0 (rarest possible) for a new player

    def test_guess_count_increment(self):
        # Test that guess count increments correctly
        result = GameResult.objects.create(
            date=date.today(),
            cell_key="0_0",
            player=self.player1,
            guess_count=1
        )
        result.guess_count = F('guess_count') + 1
        result.save()
        result.refresh_from_db()
        self.assertEqual(result.guess_count, 2)

    def test_initialize_scores_from_recent_games(self):
        # Clean up any existing records
        GameResult.objects.all().delete()
        
        game_factor = 1
        
        # Create test dates for the last 5 games
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(1, 6)]
        
        # Create test players
        player1 = Player.objects.create(stats_id=1, name="Player 1")
        player2 = Player.objects.create(stats_id=2, name="Player 2")
        player3 = Player.objects.create(stats_id=3, name="Player 3")
        
        # Create game results:
        # Player 1: appears in games 1, 2, 3 (should get count=3)
        # Player 2: appears in games 1, 2, 3, 4 (should get count=4)
        # Player 3: appears in games 2, 3 (should get count=2)
        
        # Game 1 (yesterday)
        GameResult.objects.create(date=dates[0], cell_key="0_0", player=player1, guess_count=10)
        GameResult.objects.create(date=dates[0], cell_key="0_0", player=player2, guess_count=9)
        
        # Game 2 (2 days ago)
        GameResult.objects.create(date=dates[1], cell_key="0_0", player=player1, guess_count=8)
        GameResult.objects.create(date=dates[1], cell_key="0_0", player=player2, guess_count=7)
        GameResult.objects.create(date=dates[1], cell_key="0_0", player=player3, guess_count=6)
        
        # Game 3 (3 days ago)
        GameResult.objects.create(date=dates[2], cell_key="0_0", player=player1, guess_count=5)
        GameResult.objects.create(date=dates[2], cell_key="0_0", player=player2, guess_count=4)
        GameResult.objects.create(date=dates[2], cell_key="0_0", player=player3, guess_count=3)
        
        # Game 4 (4 days ago)
        GameResult.objects.create(date=dates[3], cell_key="0_0", player=player2, guess_count=2)
        
        # Game 5 (5 days ago) - no relevant results
        
        # Initialize scores for today
        GameResult.initialize_scores_from_recent_games(today, "0_0", game_factor=game_factor)
        
        # Verify the results
        result1 = GameResult.objects.get(date=today, cell_key="0_0", player=player1)
        self.assertEqual(result1.guess_count, 3*game_factor, "Player 1 should have count=9 (3 games * factor 3)")
        
        result2 = GameResult.objects.get(date=today, cell_key="0_0", player=player2)
        self.assertEqual(result2.guess_count, 4*game_factor, "Player 2 should have count=12 (4 games * factor 3)")
        
        result3 = GameResult.objects.get(date=today, cell_key="0_0", player=player3)
        self.assertEqual(result3.guess_count, 2*game_factor, "Player 3 should have count=6 (2 games * factor 3)")
        
        # Test initialization for a different cell
        GameResult.initialize_scores_from_recent_games(today, "1_1", game_factor=game_factor)
        
        # Verify the same counts are used for the new cell
        result = GameResult.objects.get(date=today, cell_key="1_1", player=player2)
        self.assertEqual(result.guess_count, 4*game_factor, "Player 2 should have count=12 (4 games * factor 3) in new cell")

class GameFilterTests(TestCase):
    def setUp(self):
        # Clean up any existing records
        GameFilterDB.objects.all().delete()
        GameResult.objects.all().delete()
        
        # Create test teams and players
        populate_teams(30)
        populate_players(100)
        
        # Set test date
        self.test_date = date.today()
        
    def test_filter_persistence(self):
        # Create a game builder and generate filters
        builder = GameBuilder(0)
        static_filters, dynamic_filters = builder.get_tuned_filters(date.today())
        
        # Verify filters were saved to database
        db_filters = GameFilterDB.objects.filter(date=self.test_date)
        self.assertEqual(db_filters.count(), 6)  # 3 static + 3 dynamic filters
        
        # Verify filter types and counts
        static_count = db_filters.filter(filter_type='static').count()
        dynamic_count = db_filters.filter(filter_type='dynamic').count()
        self.assertEqual(static_count, 3)
        self.assertEqual(dynamic_count, 3)
        
        # Verify filter indices
        for i in range(3):
            self.assertTrue(db_filters.filter(filter_type='static', filter_index=i).exists())
            self.assertTrue(db_filters.filter(filter_type='dynamic', filter_index=i).exists())
            
    def test_filter_reconstruction(self):
        # First create and save filters
        builder1 = GameBuilder(0)
        static_filters1, dynamic_filters1 = builder1.get_tuned_filters(date.today())
        
        # Create a new builder and get filters - should reconstruct from database
        builder2 = GameBuilder(1)  # Different seed shouldn't matter
        static_filters2, dynamic_filters2 = builder2.get_tuned_filters(date.today())
        
        # Verify the filters are the same
        self.assertEqual(len(static_filters1), len(static_filters2))
        self.assertEqual(len(dynamic_filters1), len(dynamic_filters2))
        
        # Verify filter descriptions match
        for i in range(3):
            self.assertEqual(static_filters1[i].get_desc(), static_filters2[i].get_desc())
            self.assertEqual(dynamic_filters1[i].get_desc(), dynamic_filters2[i].get_desc())
            
    def test_filter_config_storage(self):
        # Create and save filters
        builder = GameBuilder(0)
        static_filters, dynamic_filters = builder.get_tuned_filters(date.today())
        
        # Get filters from database
        db_filters = GameFilterDB.objects.filter(date=self.test_date)
        
        # Verify filter configurations are stored correctly
        for db_filter in db_filters:
            filter_obj = create_filter_from_db(db_filter)
            
            # Verify the filter can be reconstructed and works
            players = Player.objects.all()
            filtered_players = filter_obj.apply_filter(players)
            self.assertGreater(len(filtered_players), 0)
            
    def test_filter_uniqueness(self):
        # Create filters for today
        builder1 = GameBuilder(0)
        builder1.get_tuned_filters(date.today())
        
        # Try to create filters for the same date with a different seed
        builder2 = GameBuilder(1)
        static_filters2, dynamic_filters2 = builder2.get_tuned_filters(date.today())
        
        # Verify we got the same filters back (from database) instead of new ones
        db_filters = GameFilterDB.objects.filter(date=self.test_date)
        self.assertEqual(db_filters.count(), 6)  # Still only 6 filters
        
        # Verify the filters are the same as what we got back
        for db_filter in db_filters:
            filter_obj = create_filter_from_db(db_filter)
            
            if db_filter.filter_type == 'static':
                self.assertTrue(any(f.get_desc() == filter_obj.get_desc() for f in static_filters2))
            else:
                self.assertTrue(any(f.get_desc() == filter_obj.get_desc() for f in dynamic_filters2))
