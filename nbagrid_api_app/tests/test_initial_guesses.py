from django.test import TestCase
from datetime import date
from nbagrid_api_app.models import GameResult, Player, Team, GameGrid


class InitialGuessesTestCase(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create a test team
        self.team = Team.objects.create(stats_id=1610612737, name="Atlanta Hawks", abbr="ATL")
        
        # Create test players
        self.player1 = Player.active.create(
            stats_id=203076,
            name="John Doe"
        )
        self.player1.teams.add(self.team)
        
        self.player2 = Player.active.create(
            stats_id=203077,
            name="Jane Smith"
        )
        self.player2.teams.add(self.team)
        
        self.test_date = date.today()
        self.cell_key = "0_0"

    def test_initial_guesses_field_default(self):
        """Test that initial_guesses field defaults to 0."""
        result = GameResult.objects.create(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1,
            guess_count=5
        )
        
        self.assertEqual(result.initial_guesses, 0)
        self.assertEqual(result.user_guesses, 5)

    def test_user_guesses_property(self):
        """Test that user_guesses property calculates correctly."""
        result = GameResult.objects.create(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1,
            guess_count=10,
            initial_guesses=3
        )
        
        self.assertEqual(result.user_guesses, 7)

    def test_user_guesses_negative_protection(self):
        """Test that user_guesses never goes negative."""
        result = GameResult.objects.create(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1,
            guess_count=2,
            initial_guesses=5
        )
        
        self.assertEqual(result.user_guesses, 0)

    def test_initialize_scores_sets_initial_guesses(self):
        """Test that initialize_scores_from_recent_games sets initial_guesses correctly."""
        # Create some historical data
        GameResult.objects.create(
            date=self.test_date - date.resolution,
            cell_key=self.cell_key,
            player=self.player1,
            guess_count=10
        )
        GameResult.objects.create(
            date=self.test_date - date.resolution,
            cell_key=self.cell_key,
            player=self.player2,
            guess_count=5
        )
        
        # Initialize scores for today
        GameResult.initialize_scores_from_recent_games(
            date=self.test_date,
            cell_key=self.cell_key,
            game_factor=2
        )
        
        # Check that initial_guesses were set correctly
        result1 = GameResult.objects.get(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1
        )
        result2 = GameResult.objects.get(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player2
        )
        
        # player1 should have higher initial_guesses than player2 (based on historical data)
        self.assertGreater(result1.initial_guesses, result2.initial_guesses)
        self.assertEqual(result1.guess_count, result1.initial_guesses)
        self.assertEqual(result2.guess_count, result2.initial_guesses)

    def test_string_representation(self):
        """Test that the string representation includes all guess counts."""
        result = GameResult.objects.create(
            date=self.test_date,
            cell_key=self.cell_key,
            player=self.player1,
            guess_count=10,
            initial_guesses=3
        )
        
        str_repr = str(result)
        self.assertIn("10 correct", str_repr)
        self.assertIn("3 initial", str_repr)
        self.assertIn("7 user", str_repr)
        self.assertIn("0 wrong", str_repr)

    def test_admin_user_guesses_display(self):
        """Test that the admin can correctly calculate and display user guesses."""
        from nbagrid_api_app.models import GameGrid
        
        # Create GameResult objects with different initial_guesses
        GameResult.objects.create(
            date=self.test_date,
            cell_key="0_0",
            player=self.player1,
            guess_count=10,
            initial_guesses=3
        )
        GameResult.objects.create(
            date=self.test_date,
            cell_key="0_1",
            player=self.player2,
            guess_count=8,
            initial_guesses=2
        )
        
        # Create a GameGrid for this date
        game_grid = GameGrid.objects.create(
            date=self.test_date,
            cell_correct_players={"0_0": 1, "0_1": 1}
        )
        
        # Test that the admin properties work correctly
        self.assertEqual(game_grid.total_guesses, 18)  # 10 + 8
        self.assertEqual(game_grid.total_user_guesses, 13)  # (10-3) + (8-2)
        self.assertEqual(game_grid.total_wrong_guesses, 0)  # No wrong guesses yet

    def test_wrong_guesses_functionality(self):
        """Test that wrong guesses are properly recorded and counted."""
        # Test recording wrong guesses
        result1 = GameResult.record_wrong_guess(self.test_date, self.cell_key, self.player1)
        self.assertEqual(result1.wrong_guesses, 1)
        
        # Test incrementing wrong guesses
        result2 = GameResult.record_wrong_guess(self.test_date, self.cell_key, self.player1)
        self.assertEqual(result2.wrong_guesses, 2)
        
        # Test recording wrong guesses for different player
        result3 = GameResult.record_wrong_guess(self.test_date, self.cell_key, self.player2)
        self.assertEqual(result3.wrong_guesses, 1)
        
        # Test total wrong guesses count
        total_wrong = GameResult.get_total_wrong_guesses(self.test_date)
        self.assertEqual(total_wrong, 3)  # 2 + 1
        
        # Test GameGrid property
        game_grid = GameGrid.objects.create(
            date=self.test_date,
            cell_correct_players={"0_0": 1}
        )
        self.assertEqual(game_grid.total_wrong_guesses, 3)
