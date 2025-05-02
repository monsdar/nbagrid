
from django.test import TestCase

from nbagrid_api_app.models import Player, Team

from nbagrid_api_app.GameFilter import DynamicGameFilter
from nbagrid_api_app.GameFilter import PositionFilter
from nbagrid_api_app.GameFilter import CountryFilter
from nbagrid_api_app.GameFilter import USAFilter
from nbagrid_api_app.GameFilter import InternationalFilter
from nbagrid_api_app.GameFilter import TeamFilter
from nbagrid_api_app.GameFilter import Top10DraftpickFilter
from nbagrid_api_app.GameFilter import TeamCountFilter
from nbagrid_api_app.GameFilter import AllNbaFilter
from nbagrid_api_app.GameFilter import AllDefensiveFilter
from nbagrid_api_app.GameFilter import AllRookieFilter
from nbagrid_api_app.GameFilter import NbaChampFilter
from nbagrid_api_app.GameFilter import AllStarFilter
from nbagrid_api_app.GameFilter import OlympicMedalFilter

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

class Top10DraftpickFilterTest(TestCase):
    def setUp(self):
        # Create test players with different draft numbers
        self.player1 = Player.objects.create(
            stats_id=1,
            name="Player 1",
            draft_number=1,  # Top 10 pick
            draft_year=2020
        )
        self.player2 = Player.objects.create(
            stats_id=2,
            name="Player 2",
            draft_number=15,  # Not a top 10 pick
            draft_year=2020
        )
        self.player3 = Player.objects.create(
            stats_id=3,
            name="Player 3",
            draft_number=10,  # Edge case - exactly 10
            draft_year=2020
        )
        self.player4 = Player.objects.create(
            stats_id=4,
            name="Player 4",
            draft_number=5,  # Top 10 pick
            draft_year=2019
        )
        self.player5 = Player.objects.create(
            stats_id=5,
            name="Player 5",
            is_undrafted=True
        )

    def test_filter_top_10_picks(self):
        filter = Top10DraftpickFilter()
        queryset = filter.apply_filter(Player.objects.all())
        
        # Should include players with draft number <= 10
        self.assertIn(self.player1, queryset)
        self.assertIn(self.player3, queryset)
        self.assertIn(self.player4, queryset)
        
        # Should exclude players with draft number > 10
        self.assertNotIn(self.player2, queryset)
        
        # Should exclude undrafted players
        self.assertNotIn(self.player5, queryset)

    def test_filter_description(self):
        filter = Top10DraftpickFilter()
        desc = filter.get_desc()
        self.assertEqual(desc, "Top 10 Draft Pick")

    def test_player_stats_string(self):
        filter = Top10DraftpickFilter()
        
        # Test with a top 10 pick
        stats_str = filter.get_player_stats_str(self.player1)
        self.assertEqual(stats_str, "Draft Pick: #1 in 2020")
        
        # Test with a non-top 10 pick
        stats_str = filter.get_player_stats_str(self.player2)
        self.assertEqual(stats_str, "Draft Pick: #15 in 2020")
        
        # Test with an undrafted player
        stats_str = filter.get_player_stats_str(self.player5)
        self.assertEqual(stats_str, "Draft Pick: Undrafted") 

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
        
class USAFilterTest(TestCase):
    def setUp(self):
        # Create test players
        self.usa_player1 = Player.objects.create(
            stats_id=1,
            name='USA Player 1',
            country='USA'
        )
        self.usa_player2 = Player.objects.create(
            stats_id=2,
            name='USA Player 2',
            country='USA'
        )
        self.int_player1 = Player.objects.create(
            stats_id=3,
            name='International Player 1',
            country='Canada'
        )
        self.int_player2 = Player.objects.create(
            stats_id=4,
            name='International Player 2',
            country='France'
        )

    def test_usafilter(self):
        """Test that USAFilter correctly filters USA players."""
        usa_filter = USAFilter()
        
        # Test with USA players
        self.assertTrue(usa_filter.apply_filter(Player.objects.filter(stats_id=1)).exists())
        self.assertTrue(usa_filter.apply_filter(Player.objects.filter(stats_id=2)).exists())
        
        # Test with international players
        self.assertFalse(usa_filter.apply_filter(Player.objects.filter(stats_id=3)).exists())
        self.assertFalse(usa_filter.apply_filter(Player.objects.filter(stats_id=4)).exists())
        
        # Test description
        self.assertEqual(usa_filter.get_desc(), "Born in USA")

class InternationalFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(100):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='USA')
        for index in range(200, 210):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Germany')
        for index in range(300, 310):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Ghana')
        for index in range(400, 410):
            Player.objects.create(stats_id=index, name=f'Player {index}', country='Mexico')
    
    def test_internationalfilter(self):
        filter = InternationalFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 30)  # Should match non-USA players
        self.assertTrue(all(p.country != 'USA' for p in filtered_players))

class AllNbaFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(10):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_nba_first=True)
        for index in range(10, 20):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_nba_second=True)
        for index in range(20, 30):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_nba_third=True)
        for index in range(30, 40):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No All-NBA awards
    
    def test_allnba_filter(self):
        filter = AllNbaFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 30)  # Should match all All-NBA players
        self.assertTrue(all(p.is_award_all_nba_first or p.is_award_all_nba_second or p.is_award_all_nba_third for p in filtered_players))

class AllDefensiveFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(20):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_defensive=True)
        for index in range(20, 40):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No All-Defensive awards
    
    def test_alldefensive_filter(self):
        filter = AllDefensiveFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 20)  # Should match All-Defensive players
        self.assertTrue(all(p.is_award_all_defensive for p in filtered_players))

class AllRookieFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(15):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_rookie=True)
        for index in range(15, 30):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No All-Rookie awards
    
    def test_allrookie_filter(self):
        filter = AllRookieFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 15)  # Should match All-Rookie players
        self.assertTrue(all(p.is_award_all_rookie for p in filtered_players))

class NbaChampFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(25):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_champ=True)
        for index in range(25, 50):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No championships
    
    def test_nbachamp_filter(self):
        filter = NbaChampFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 25)  # Should match NBA champions
        self.assertTrue(all(p.is_award_champ for p in filtered_players))

class AllStarFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(30):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_all_star=True)
        for index in range(30, 60):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No All-Star appearances
    
    def test_allstar_filter(self):
        filter = AllStarFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 30)  # Should match All-Star players
        self.assertTrue(all(p.is_award_all_star for p in filtered_players))

class OlympicMedalFilterTest(TestCase):
    def setUp(self):
        # Create test players
        for index in range(10):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_olympic_gold_medal=True)
        for index in range(10, 20):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_olympic_silver_medal=True)
        for index in range(20, 30):
            Player.objects.create(stats_id=index, name=f'Player {index}', is_award_olympic_bronze_medal=True)
        for index in range(30, 40):
            Player.objects.create(stats_id=index, name=f'Player {index}')  # No Olympic medals
    
    def test_olympicmedal_filter(self):
        filter = OlympicMedalFilter()
        filtered_players = filter.apply_filter(Player.objects.all())
        self.assertEqual(filtered_players.count(), 30)  # Should match all Olympic medalists
        self.assertTrue(all(p.is_award_olympic_gold_medal or p.is_award_olympic_silver_medal or p.is_award_olympic_bronze_medal for p in filtered_players))

class CombinedFilterTest(TestCase):
    def test_team_and_team_count_filter_combination(self):
        """Test that TeamFilter and TeamCountFilter work correctly when combined."""
        # Create test teams
        team1 = Team.objects.create(stats_id=1, name='Team 1', abbr='T1')
        team2 = Team.objects.create(stats_id=2, name='Team 2', abbr='T2')
        team3 = Team.objects.create(stats_id=3, name='Team 3', abbr='T3')
        
        # Create test players with different team combinations
        # Player 1: Only on Team 1
        player1 = Player.objects.create(stats_id=1, name='Player 1')
        player1.teams.set([team1])
        
        # Player 2: On Team 1 and 2 (2 teams)
        player2 = Player.objects.create(stats_id=2, name='Player 2')
        player2.teams.set([team1, team2])
        
        # Player 3: On Team 2 and 3 (2 teams)
        player3 = Player.objects.create(stats_id=3, name='Player 3')
        player3.teams.set([team2, team3])
        
        # Player 4: On all three teams (3 teams)
        player4 = Player.objects.create(stats_id=4, name='Player 4')
        player4.teams.set([team1, team2, team3])
        
        # Create TeamFilter for Team 1
        team_filter = TeamFilter(seed=0)
        team_filter.team_name = 'Team 1'
        
        # Create TeamCountFilter for 2+ teams
        team_count_filter = TeamCountFilter({
            'description': 'teams played for',
            'initial_min_value': 2,
            'initial_max_value': 8,
            'initial_value_step': 1,
            'widen_step': 1,
            'narrow_step': 1
        })
        team_count_filter.current_value = 2  # 2 or more teams
        
        # Apply filters individually
        team_filter_players = team_filter.apply_filter(Player.objects.all())
        self.assertEqual(team_filter_players.count(), 3)  # Players 1, 2, and 4 played for Team 1
        
        team_count_filter_players = team_count_filter.apply_filter(Player.objects.all())
        self.assertEqual(team_count_filter_players.count(), 3)  # Players 2, 3, and 4 played for 2+ teams
        
        # Apply filters in sequence (simulating how they'd be applied in a grid cell)
        matching_players = Player.objects.all()
        matching_players = team_filter.apply_filter(matching_players)
        matching_players = team_count_filter.apply_filter(matching_players)
        
        # Should match players who both played for Team 1 AND played for 2+ teams
        self.assertEqual(matching_players.count(), 2)  # Players 2 and 4
        player_ids = set(matching_players.values_list('stats_id', flat=True))
        self.assertIn(2, player_ids)  # Player 2 should match
        self.assertIn(4, player_ids)  # Player 4 should match
        
        # Test the reverse order to ensure it doesn't matter
        matching_players = Player.objects.all()
        matching_players = team_count_filter.apply_filter(matching_players)
        matching_players = team_filter.apply_filter(matching_players)
        
        self.assertEqual(matching_players.count(), 2)  # Should still be Players 2 and 4
        player_ids = set(matching_players.values_list('stats_id', flat=True))
        self.assertIn(2, player_ids)
        self.assertIn(4, player_ids)
