from django.test import TestCase
from django.utils import timezone
import datetime

from nbagrid_api_app.models import GameGrid, Player, Team, GameResult, GameCompletion, GameFilterDB
from nbagrid_api_app.GameBuilder import GameBuilder

class GameGridModelTest(TestCase):
    """
    Test cases for GameGrid model functionality
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        Set up data for all test methods
        """
        # Create test players
        team = Team.objects.create(stats_id=1, name="Test Team", abbr="TTT")
        
        for i in range(1, 11):
            player = Player.objects.create(
                stats_id=i,
                name=f"Test Player {i}",
                display_name=f"T. Player {i}",
                position="G" if i < 5 else ("F" if i < 8 else "C")
            )
            player.teams.add(team)
            player.save()
        
        # Create a test game date
        cls.test_date = datetime.date(2025, 5, 1)
        
    def setUp(self):
        """
        Set up data for each test method
        """
        self.grid = GameGrid.objects.create(
            date=self.test_date,
            grid_size=3,
            cell_correct_players={
                "0_0": 5,
                "0_1": 3,
                "0_2": 7,
                "1_0": 2,
                "1_1": 4,
                "1_2": 6,
                "2_0": 1,
                "2_1": 8,
                "2_2": 9
            }
        )
        
        # Create some game results
        player1 = Player.objects.get(stats_id=1)
        player2 = Player.objects.get(stats_id=2)
        
        # Create multiple guesses for the same player in cell "0_0"
        GameResult.objects.create(date=self.test_date, cell_key="0_0", player=player1, guess_count=5)
        
        # Create a single guess for another player in cell "0_1"
        GameResult.objects.create(date=self.test_date, cell_key="0_1", player=player2, guess_count=1)
        
        # Create a game completion
        GameCompletion.objects.create(date=self.test_date, session_key="test_session_1")
        GameCompletion.objects.create(date=self.test_date, session_key="test_session_2")
        
    def test_grid_creation(self):
        """Test that a grid can be created with cell_correct_players data"""
        self.assertEqual(self.grid.date, self.test_date)
        self.assertEqual(self.grid.grid_size, 3)
        self.assertEqual(self.grid.cell_correct_players["0_0"], 5)
        self.assertEqual(self.grid.cell_correct_players["2_2"], 9)
    
    def test_total_correct_players(self):
        """Test that total_correct_players calculates the sum correctly"""
        self.assertEqual(self.grid.total_correct_players, 45)  # Sum of all values in cell_correct_players
    
    def test_total_guesses(self):
        """Test that total_guesses calculates correctly from GameResult"""
        self.assertEqual(self.grid.total_guesses, 6)  # 5 + 1 = 6
    
    def test_completion_count(self):
        """Test that completion_count is calculated correctly"""
        self.assertEqual(self.grid.completion_count, 2)
        
        # Add another completion
        GameCompletion.objects.create(date=self.test_date, session_key="test_session_3")
        
        # Verify the count increases
        self.assertEqual(self.grid.completion_count, 3)
    
    def test_empty_grid(self):
        """Test a grid with no cell data"""
        empty_date = self.test_date + datetime.timedelta(days=2)
        empty_grid = GameGrid.objects.create(
            date=empty_date,
            grid_size=3,
            cell_correct_players={}
        )
        
        # Total correct players should be 0
        self.assertEqual(empty_grid.total_correct_players, 0)
        
        # Total guesses should be 0 if no GameResults exist
        self.assertEqual(empty_grid.total_guesses, 0)
    
    def test_cell_key_access(self):
        """Test accessing cell data by key"""
        # Test existing cell key
        self.assertEqual(self.grid.cell_correct_players.get("0_0"), 5)
        
        # Test non-existing cell key
        self.assertIsNone(self.grid.cell_correct_players.get("9_9"))
    
    def test_gamegrid_with_gamebuilder(self):
        """Test integration with GameBuilder"""
        # First, create some game filters to simulate a generated game
        tomorrow = self.test_date + datetime.timedelta(days=1)
        
        # Create simple filter configurations
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='static',
            filter_class='PositionFilter',
            filter_config={'positions': ['Guard']},
            filter_index=0
        )
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='static',
            filter_class='PositionFilter',
            filter_config={'positions': ['Forward']},
            filter_index=1
        )
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='static',
            filter_class='PositionFilter',
            filter_config={'positions': ['Center']},
            filter_index=2
        )
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='dynamic',
            filter_class='PositionFilter',
            filter_config={'positions': ['Guard']},
            filter_index=3
        )
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='dynamic',
            filter_class='PositionFilter',
            filter_config={'positions': ['Forward']},
            filter_index=4
        )
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type='dynamic',
            filter_class='PositionFilter',
            filter_config={'positions': ['Center']},
            filter_index=5
        )
        # Create a GameBuilder to test integration
        builder = GameBuilder(random_seed=42)
        
        # This should use the existing filters and create a GameGrid
        static_filters, dynamic_filters = builder.get_tuned_filters(tomorrow)
        
        # Check if a GameGrid was created for tomorrow
        game_grid = GameGrid.objects.get(date=tomorrow)
        
        # Check that cell_correct_players contains data
        self.assertTrue(len(game_grid.cell_correct_players) > 0) 