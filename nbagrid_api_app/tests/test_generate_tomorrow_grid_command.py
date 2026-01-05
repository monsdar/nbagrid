from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from nbagrid_api_app.GameBuilder import GameBuilder
from nbagrid_api_app.GameFilter import GameFilter
from nbagrid_api_app.models import GameFilterDB, Player


class MockFilter(GameFilter):
    """Mock filter for testing purposes."""
    def __init__(self, description):
        self.description = description

    def get_desc(self):
        return self.description
    
    def get_detailed_desc(self):
        return f"Detailed: {self.description}"
    
    def get_filter_type_description(self):
        return self.description

    def apply_filter(self, queryset):
        return queryset


class GenerateTomorrowGridCommandTests(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create a test player so that filters can work
        self.player = Player.active.create(
            stats_id=1,
            name="Test Player",
            position="Guard",
            country="USA",
            career_ppg=20,
            career_rpg=6,
            career_apg=4,
            career_gp=200,
        )
        
        # Calculate tomorrow's date for testing
        self.tomorrow_date = datetime.now().date() + timedelta(days=1)

    def tearDown(self):
        """Clean up test data."""
        GameFilterDB.objects.all().delete()
        Player.active.all().delete()

    def test_command_generates_grid_when_none_exists(self):
        """Test that the command generates a grid when one doesn't exist for tomorrow."""
        # Ensure no grid exists for tomorrow
        self.assertFalse(GameFilterDB.objects.filter(date=self.tomorrow_date).exists())
        
        # Mock the GameBuilder class entirely to avoid complex filter logic
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            # Create mock filters
            mock_static = [MockFilter("LAL"), MockFilter("BOS"), MockFilter("GSW")]
            mock_dynamic = [MockFilter("MIA"), MockFilter("CHI"), MockFilter("NYK")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            # Run the command
            out = StringIO()
            call_command('generate_tomorrow_grid', stdout=out)
            
            # Verify the command ran successfully
            output = out.getvalue()
            self.assertIn("Successfully generated grid", output)
            self.assertIn(str(self.tomorrow_date), output)
            
            # Verify get_tuned_filters was called
            mock_builder.get_tuned_filters.assert_called_once()

    def test_command_skips_generation_when_grid_exists(self):
        """Test that the command does nothing when a grid already exists for tomorrow."""
        # Create a grid for tomorrow
        GameFilterDB.objects.create(
            date=self.tomorrow_date,
            filter_type="static",
            filter_class="TeamFilter",
            filter_config={"team_abbreviation": "LAL"},
            filter_index=0,
        )
        
        # Run the command
        out = StringIO()
        call_command('generate_tomorrow_grid', stdout=out)
        
        # Verify the command skipped generation
        output = out.getvalue()
        self.assertIn("already exists", output)
        self.assertIn("Nothing to do", output)

    def test_command_calculates_tomorrow_date_correctly(self):
        """Test that the command correctly calculates tomorrow's date."""
        expected_tomorrow = datetime.now().date() + timedelta(days=1)
        
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_static = [MockFilter("LAL")]
            mock_dynamic = [MockFilter("BOS")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', stdout=out)
            
            output = out.getvalue()
            self.assertIn(str(expected_tomorrow), output)

    def test_command_uses_correct_seed(self):
        """Test that the command uses tomorrow's date as the seed."""
        tomorrow_datetime = datetime.combine(self.tomorrow_date, datetime.min.time())
        expected_seed = int(tomorrow_datetime.timestamp())
        
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = ([MockFilter("LAL")], [MockFilter("BOS")])
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', stdout=out)
            
            # Verify GameBuilder was initialized with correct seed
            mock_builder_class.assert_called_once_with(random_seed=expected_seed)

    def test_command_handles_generation_failure(self):
        """Test that the command handles generation failures gracefully."""
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            # Simulate a failure by raising an exception
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.side_effect = Exception("Generation failed")
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            err = StringIO()
            
            # Command should exit with error code
            with self.assertRaises(SystemExit) as cm:
                call_command('generate_tomorrow_grid', stdout=out, stderr=err)
            
            # Verify exit code is 1 (failure)
            self.assertEqual(cm.exception.code, 1)
            
            # Verify error message
            output = out.getvalue()
            self.assertIn("Error generating grid", output)

    def test_command_handles_none_filters(self):
        """Test that the command handles None filters from get_tuned_filters."""
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            # Return None filters to simulate failure
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (None, None)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            
            # Command should exit with error code
            with self.assertRaises(SystemExit) as cm:
                call_command('generate_tomorrow_grid', stdout=out)
            
            # Verify exit code is 1 (failure)
            self.assertEqual(cm.exception.code, 1)
            
            # Verify error message
            output = out.getvalue()
            self.assertIn("Failed to generate grid", output)

    def test_command_displays_generated_filters(self):
        """Test that the command displays the generated filters in output."""
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_static = [MockFilter("LAL"), MockFilter("BOS")]
            mock_dynamic = [MockFilter("GSW"), MockFilter("MIA")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', stdout=out)
            
            output = out.getvalue()
            # Check that filter descriptions are shown
            self.assertIn("Static filters:", output)
            self.assertIn("Dynamic filters:", output)

    def test_command_next_missing_finds_first_gap(self):
        """Test that --next-missing finds the first date without a grid."""
        # Create grids for tomorrow and day after tomorrow
        tomorrow = datetime.now().date() + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)
        day_after_that = day_after + timedelta(days=1)
        
        # Create grids for tomorrow and day after tomorrow (skipping day_after_that)
        GameFilterDB.objects.create(
            date=tomorrow,
            filter_type="static",
            filter_class="TeamFilter",
            filter_config={"team_abbreviation": "LAL"},
            filter_index=0,
        )
        GameFilterDB.objects.create(
            date=day_after,
            filter_type="static",
            filter_class="TeamFilter",
            filter_config={"team_abbreviation": "BOS"},
            filter_index=0,
        )
        
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_static = [MockFilter("GSW")]
            mock_dynamic = [MockFilter("MIA")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', '--next-missing', stdout=out)
            
            output = out.getvalue()
            # Should find and generate for day_after_that
            self.assertIn(str(day_after_that), output)
            self.assertIn("Found next missing date", output)
            self.assertIn("Successfully generated grid", output)

    def test_command_next_missing_with_no_gaps(self):
        """Test that --next-missing handles case where all dates have grids."""
        # Create grids for many days ahead
        for i in range(1, 366):  # Fill 365 days
            future_date = datetime.now().date() + timedelta(days=i)
            GameFilterDB.objects.create(
                date=future_date,
                filter_type="static",
                filter_class="TeamFilter",
                filter_config={"team_abbreviation": "LAL"},
                filter_index=0,
            )
        
        out = StringIO()
        call_command('generate_tomorrow_grid', '--next-missing', stdout=out)
        
        output = out.getvalue()
        self.assertIn("All dates up to 365 days ahead already have grids", output)

    def test_command_next_missing_uses_recent_weights(self):
        """Test that --next-missing reports using recent grids (last 7 days) for weights."""
        # Create a grid for yesterday to provide recent context
        yesterday = datetime.now().date() - timedelta(days=1)
        GameFilterDB.objects.create(
            date=yesterday,
            filter_type="static",
            filter_class="TeamFilter",
            filter_config={"team_abbreviation": "LAL"},
            filter_index=0,
        )
        
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_static = [MockFilter("GSW")]
            mock_dynamic = [MockFilter("MIA")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', '--next-missing', stdout=out)
            
            output = out.getvalue()
            # Should mention using recent grids (last 7 days) for variety
            self.assertIn("last 7 days", output.lower())
            self.assertIn("ensure variety", output.lower())
    
    def test_command_next_missing_no_recent_grids(self):
        """Test that --next-missing handles case with no recent grids."""
        # Don't create any recent grids - simulate first week of generation
        
        with patch('nbagrid_api_app.management.commands.generate_tomorrow_grid.GameBuilder') as mock_builder_class:
            mock_static = [MockFilter("GSW")]
            mock_dynamic = [MockFilter("MIA")]
            
            mock_builder = MagicMock()
            mock_builder.get_tuned_filters.return_value = (mock_static, mock_dynamic)
            mock_builder_class.return_value = mock_builder
            
            out = StringIO()
            call_command('generate_tomorrow_grid', '--next-missing', stdout=out)
            
            output = out.getvalue()
            # Should mention no recent grids found
            self.assertIn("no recent grids", output.lower())
            self.assertIn("without weight adjustments", output.lower())

