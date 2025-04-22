from django.test import TestCase

from nbagrid_api_app.GameFilter import DynamicGameFilter, PositionFilter, CountryFilter, TeamFilter, BooleanFilter, TeamCountFilter
from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.models import Player, Team, GameResult
from nba_api.stats.endpoints import commonplayerinfo, playercareerstats
from datetime import date

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
                                               weights=   [ 0.01, 0.99],
                                               k=1)[0]
        player.save()
        
class DynamicGameFilterTest(TestCase):
    def test_numeric_filter(self):
        # Create test players with different career PPG values
        Player.objects.create(stats_id=1, name='Player 1', career_ppg=24)
        Player.objects.create(stats_id=2, name='Player 2', career_ppg=25)
        Player.objects.create(stats_id=3, name='Player 3', career_ppg=26)
        
        # Create a filter for points per game
        filter = DynamicGameFilter({
            'field': 'career_ppg',
            'description': 'Career points per game:',
            'initial_min_value': 10,
            'initial_max_value': 30,
            'initial_value_step': 2,
            'widen_step': 2,
            'narrow_step': 2
        })
        filter.current_value = 25  # Set a specific value for testing
        
        # Test filter description
        self.assertEqual(filter.get_desc(), "Career points per game: 25+")
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 2)
        self.assertTrue(all(p.career_ppg >= 25 for p in filtered_players))
        
        # Test filter widening
        filter.widen_filter()
        self.assertEqual(filter.current_value, 23)
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 3)
        
        # Test filter narrowing
        filter.narrow_filter()
        self.assertEqual(filter.current_value, 25)
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 2)

class PositionFilterTest(TestCase):
    def test_position_filter(self):
        # Create test players with different positions
        Player.objects.create(stats_id=1, name='Player 1', position='Guard')
        Player.objects.create(stats_id=2, name='Player 2', position='Forward')
        Player.objects.create(stats_id=3, name='Player 3', position='Center')
        
        # Create a position filter with a fixed seed
        filter = PositionFilter(seed=0)
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 1)
        self.assertTrue(filtered_players.first().position == filter.selected_position)

class CountryFilterTest(TestCase):
    def test_country_filter(self):
        # Create test players from different countries
        for index in range(100):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='USA')
        for index in range(200, 210):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Germany')
        for index in range(300, 310):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Ghana')
        for index in range(400, 410):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Mexico')
        
        # Create a country filter with a fixed seed
        filter = CountryFilter(seed=0)
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 100)  # Should match the number of players from the selected country

class TeamFilterTest(TestCase):
    def test_team_filter(self):
        # Create test teams and players
        team1 = Team.objects.create(stats_id=1, name='Team 1', abbr='T1')
        team2 = Team.objects.create(stats_id=2, name='Team 2', abbr='T2')
        
        player1 = Player.objects.create(stats_id=1, name='Player 1')
        player1.teams.set([team1])
        player2 = Player.objects.create(stats_id=2, name='Player 2')
        player2.teams.set([team2])
        player3 = Player.objects.create(stats_id=3, name='Player 3')
        player3.teams.set([team1, team2])
        
        # Create a team filter with a fixed seed
        filter = TeamFilter(seed=0)
        filter.team_name = 'Team 1'  # Set a specific team for testing
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 2)  # Should match players who played for Team 1

class BooleanFilterTest(TestCase):
    def test_boolean_filter(self):
        # Create test players with different draft rounds
        Player.objects.create(stats_id=1, name='Player 1', draft_round=1)
        Player.objects.create(stats_id=2, name='Player 2', draft_round=1)
        Player.objects.create(stats_id=3, name='Player 3', draft_round=2)
        
        # Create a boolean filter for first round picks
        filter = BooleanFilter('draft_round', 'First round draft pick', 1)
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 2)  # Should match first round picks

class TeamCountFilterTest(TestCase):
    def test_team_count_filter(self):
        # Create test teams and players
        team1 = Team.objects.create(stats_id=1, name='Team 1', abbr='T1')
        team2 = Team.objects.create(stats_id=2, name='Team 2', abbr='T2')
        team3 = Team.objects.create(stats_id=3, name='Team 3', abbr='T3')
        
        player1 = Player.objects.create(stats_id=1, name='Player 1')
        player1.teams.set([team1])
        player2 = Player.objects.create(stats_id=2, name='Player 2')
        player2.teams.set([team1, team2])
        player3 = Player.objects.create(stats_id=3, name='Player 3')
        player3.teams.set([team1, team2, team3])
        
        # Create a team count filter
        filter = TeamCountFilter({
            'description': 'teams played for',
            'initial_min_value': 2,
            'initial_max_value': 8,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1
        })
        filter.current_value = 2  # Set a specific value for testing
        
        # Test filter application
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 2)  # Should match players who played for 2+ teams

class GameBuilderTest(TestCase):
    def test_build_filter_pairs(self):
        populate_teams(30)
        populate_players(600)
        
        for index in range(10):
            builder = GameBuilder(index)
            (static_filters, dynamic_filters) = builder.get_tuned_filters()
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
        player = Player.objects.create(stats_id=202681, name='Max Mustermann')
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
        player.save()

class GameResultTests(TestCase):
    def setUp(self):
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
        result = GameResult.objects.create(date=self.test_date, cell_key=self.cell_key, player=self.player1)
        self.assertEqual(result.guess_count, 1)

        # Simulate another correct guess
        result.guess_count = GameResult.objects.get(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1
        ).guess_count + 1
        result.save()

        updated_result = GameResult.objects.get(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1
        )
        self.assertEqual(updated_result.guess_count, 2)        
