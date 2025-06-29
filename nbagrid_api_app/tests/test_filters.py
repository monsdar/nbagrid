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
from nbagrid_api_app.GameFilter import LastNameFilter

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

class LastNameFilterTest(TestCase):
    def setUp(self):
        """Set up test data with players having different last names."""
        # Create players with last names starting with different letters
        # Letter A
        for i in range(15):
            Player.objects.create(stats_id=i, name=f'First Anderson{i}', last_name=f'Anderson{i}')
        
        # Letter B
        for i in range(12):
            Player.objects.create(stats_id=100+i, name=f'First Brown{i}', last_name=f'Brown{i}')
        
        # Letter C
        for i in range(8):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=200+i, name=f'First Carter{i}', last_name=f'Carter{i}')
        
        # Letter D
        for i in range(20):
            Player.objects.create(stats_id=300+i, name=f'First Davis{i}', last_name=f'Davis{i}')
        
        # Letter E
        for i in range(5):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=400+i, name=f'First Evans{i}', last_name=f'Evans{i}')
        
        # Letter F
        for i in range(18):
            Player.objects.create(stats_id=500+i, name=f'First Fisher{i}', last_name=f'Fisher{i}')
        
        # Letter G
        for i in range(25):
            Player.objects.create(stats_id=600+i, name=f'First Garcia{i}', last_name=f'Garcia{i}')
        
        # Letter H
        for i in range(11):
            Player.objects.create(stats_id=700+i, name=f'First Harris{i}', last_name=f'Harris{i}')
        
        # Letter I
        for i in range(3):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=800+i, name=f'First Irving{i}', last_name=f'Irving{i}')
        
        # Letter J
        for i in range(16):
            Player.objects.create(stats_id=900+i, name=f'First Johnson{i}', last_name=f'Johnson{i}')
        
        # Letter K
        for i in range(14):
            Player.objects.create(stats_id=1000+i, name=f'First King{i}', last_name=f'King{i}')
        
        # Letter L
        for i in range(22):
            Player.objects.create(stats_id=1100+i, name=f'First Lee{i}', last_name=f'Lee{i}')
        
        # Letter M
        for i in range(19):
            Player.objects.create(stats_id=1200+i, name=f'First Miller{i}', last_name=f'Miller{i}')
        
        # Letter N
        for i in range(13):
            Player.objects.create(stats_id=1300+i, name=f'First Nelson{i}', last_name=f'Nelson{i}')
        
        # Letter O
        for i in range(6):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=1400+i, name=f'First Owens{i}', last_name=f'Owens{i}')
        
        # Letter P
        for i in range(17):
            Player.objects.create(stats_id=1500+i, name=f'First Parker{i}', last_name=f'Parker{i}')
        
        # Letter Q
        for i in range(2):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=1600+i, name=f'First Quinn{i}', last_name=f'Quinn{i}')
        
        # Letter R
        for i in range(21):
            Player.objects.create(stats_id=1700+i, name=f'First Roberts{i}', last_name=f'Roberts{i}')
        
        # Letter S
        for i in range(24):
            Player.objects.create(stats_id=1800+i, name=f'First Smith{i}', last_name=f'Smith{i}')
        
        # Letter T
        for i in range(15):
            Player.objects.create(stats_id=1900+i, name=f'First Taylor{i}', last_name=f'Taylor{i}')
        
        # Letter U
        for i in range(1):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=2000+i, name=f'First Underwood{i}', last_name=f'Underwood{i}')
        
        # Letter V
        for i in range(4):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=2100+i, name=f'First Vaughn{i}', last_name=f'Vaughn{i}')
        
        # Letter W
        for i in range(23):
            Player.objects.create(stats_id=2200+i, name=f'First Wilson{i}', last_name=f'Wilson{i}')
        
        # Letter X
        for i in range(1):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=2300+i, name=f'First Xavier{i}', last_name=f'Xavier{i}')
        
        # Letter Y
        for i in range(2):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=2400+i, name=f'First Young{i}', last_name=f'Young{i}')
        
        # Letter Z
        for i in range(3):  # Less than 10, should not be considered valid
            Player.objects.create(stats_id=2500+i, name=f'First Zimmerman{i}', last_name=f'Zimmerman{i}')

    def test_filter_initialization(self):
        """Test that LastNameFilter initializes correctly with a seed."""
        # Test with fixed seed for deterministic behavior
        filter1 = LastNameFilter(seed=42)
        filter2 = LastNameFilter(seed=42)
        filter3 = LastNameFilter(seed=123)
        
        # Same seed should produce same letter
        self.assertEqual(filter1.selected_letter, filter2.selected_letter)
        
        # Different seed might produce different letter
        # (though it could be the same by chance)
        
        # Selected letter should be one of the valid letters
        valid_letters = filter1._get_valid_letters()
        self.assertIn(filter1.selected_letter, valid_letters)
        self.assertIn(filter2.selected_letter, valid_letters)
        self.assertIn(filter3.selected_letter, valid_letters)

    def test_get_valid_letters(self):
        """Test that _get_valid_letters returns only letters with sufficient players."""
        filter = LastNameFilter(seed=0)
        valid_letters = filter._get_valid_letters()
        
        # Should only include letters with 10+ players
        expected_valid_letters = ['A', 'B', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'R', 'S', 'T', 'W']
        self.assertEqual(set(valid_letters), set(expected_valid_letters))
        
        # Should be sorted
        self.assertEqual(valid_letters, sorted(valid_letters))

    def test_filter_application(self):
        """Test that the filter correctly filters players by last name."""
        # Test with letter 'A'
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'A'  # Manually set for testing
        
        filtered_players = filter.apply_filter(Player.objects.all())
        
        # Should only include players with last names starting with 'A'
        self.assertEqual(filtered_players.count(), 15)  # All Anderson players
        for player in filtered_players:
            self.assertTrue(player.last_name.startswith('A'))

    def test_filter_description(self):
        """Test that the filter description is correct."""
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'J'
        
        desc = filter.get_desc()
        self.assertEqual(desc, "Last name starts with 'J'")

    def test_player_stats_string(self):
        """Test that player stats string shows correct information."""
        filter = LastNameFilter(seed=0)
        
        # Test with a player with multiple names
        player = Player.objects.create(stats_id=9999, name='Michael Jordan Jr', last_name='Jr')
        stats_str = filter.get_player_stats_str(player)
        self.assertEqual(stats_str, "Name: Jr")
        
        # Test with a player with single name (edge case)
        player2 = Player.objects.create(stats_id=9998, name='Madonna', last_name='Madonna')
        stats_str2 = filter.get_player_stats_str(player2)
        self.assertEqual(stats_str2, "Name: Madonna")

    def test_detailed_description(self):
        """Test that the detailed description is informative."""
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'S'
        
        detailed_desc = filter.get_detailed_desc()
        self.assertIn("This filter selects players whose last name starts with the letter 'S'", detailed_desc)

    def test_case_insensitive_matching(self):
        """Test that the filter works case-insensitively."""
        # Create players with mixed case last names
        Player.objects.create(stats_id=3000, name='First SMITH', last_name='SMITH')
        Player.objects.create(stats_id=3001, name='First smith', last_name='smith')
        Player.objects.create(stats_id=3002, name='First Smith', last_name='Smith')
        Player.objects.create(stats_id=3003, name='First sMiTh', last_name='sMiTh')
        
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'S'
        
        filtered_players = filter.apply_filter(Player.objects.all())
        
        # Should include all Smith variations (case-insensitive)
        # Only count the specific test players we created (stats_id 3000-3003)
        smith_players = filtered_players.filter(stats_id__in=[3000, 3001, 3002, 3003])
        self.assertEqual(smith_players.count(), 4)

    def test_edge_cases(self):
        """Test edge cases for the filter."""
        # Test with players who have very long names
        Player.objects.create(stats_id=4000, name='First Middle Last Jr Sr III', last_name='III')
        
        # Test with players who have special characters in names
        Player.objects.create(stats_id=4001, name='First O\'Connor', last_name='O\'Connor')
        Player.objects.create(stats_id=4002, name='First Van-Der-Beek', last_name='Van-Der-Beek')
        
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'I'
        
        filtered_players = filter.apply_filter(Player.objects.all())
        
        # Should include the player with 'III' as last name
        iii_players = filtered_players.filter(last_name='III')
        self.assertEqual(iii_players.count(), 1)

    def test_filter_with_realistic_data(self):
        """Test the filter with more realistic NBA player names."""
        # Create some realistic NBA player names
        realistic_names = [
            ('LeBron James', 'James'),
            ('Stephen Curry', 'Curry'),
            ('Kevin Durant', 'Durant'),
            ('Giannis Antetokounmpo', 'Antetokounmpo'),
            ('Nikola Jokic', 'Jokic'),
            ('Joel Embiid', 'Embiid'),
            ('Luka Doncic', 'Doncic'),
            ('Jayson Tatum', 'Tatum'),
            ('Devin Booker', 'Booker'),
            ('Damian Lillard', 'Lillard'),
            ('Jimmy Butler', 'Butler'),
            ('Kawhi Leonard', 'Leonard'),
            ('Paul George', 'George'),
            ('Anthony Davis', 'Davis'),
            ('Bam Adebayo', 'Adebayo')
        ]
        
        for i, (name, last_name) in enumerate(realistic_names):
            Player.objects.create(stats_id=5000+i, name=name, last_name=last_name)
        
        # Test with letter 'J'
        filter = LastNameFilter(seed=0)
        filter.selected_letter = 'J'
        
        filtered_players = filter.apply_filter(Player.objects.all())
        
        # Should include players with last names starting with 'J'
        j_players = filtered_players.filter(last_name='James')
        self.assertEqual(j_players.count(), 1)
        
        # Test with letter 'D'
        filter.selected_letter = 'D'
        filtered_players = filter.apply_filter(Player.objects.all())
        
        # Should include players with last names starting with 'D'
        d_players = filtered_players.filter(last_name='Durant')
        self.assertEqual(d_players.count(), 1)
