from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from nbagrid_api_app.models import GameFilterDB, GridMetadata


class UploadGridsToProductionCommandTests(TestCase):
    def setUp(self):
        """Set up test data."""
        # Calculate test dates
        self.today = datetime.now().date()
        self.tomorrow = self.today + timedelta(days=1)
        self.day_after = self.today + timedelta(days=2)
        
        # Create test grids in the database
        self._create_test_grid(self.today)
        self._create_test_grid(self.tomorrow)
        self._create_test_grid(self.day_after)

    def tearDown(self):
        """Clean up test data."""
        GameFilterDB.objects.all().delete()
        GridMetadata.objects.all().delete()

    def _create_test_grid(self, target_date):
        """Helper method to create a complete test grid for a given date."""
        # Create 3 static (row) filters
        for i in range(3):
            GameFilterDB.objects.create(
                date=target_date,
                filter_type='static',
                filter_class='TeamFilter',
                filter_config={'team_name': f'Team{i}'},
                filter_index=i
            )
        
        # Create 3 dynamic (column) filters
        for i in range(3):
            GameFilterDB.objects.create(
                date=target_date,
                filter_type='dynamic',
                filter_class='DynamicGameFilter',
                filter_config={'config': {'min_games': 10}, 'current_value': i},
                filter_index=i
            )
        
        # Create metadata
        GridMetadata.objects.create(
            date=target_date,
            game_title=f'Test Grid for {target_date}'
        )

    def _create_mock_response(self, status_code=200, json_data=None):
        """Helper to create a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {'status': 'success', 'message': 'Upload successful'}
        mock_response.text = 'Response text'
        return mock_response

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_upload_today_grid_success(self, mock_post):
        """Test uploading today's grid successfully."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                    '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        
        # Verify command output
        self.assertIn('Successfully uploaded', output)
        self.assertIn(str(self.today), output)
        self.assertIn('Total grids: 1', output)
        self.assertIn('Successful: 1', output)
        self.assertIn('Failed: 0', output)
        
        # Verify API was called once
        self.assertEqual(mock_post.call_count, 1)
        
        # Verify API call parameters
        call_args = mock_post.call_args
        self.assertIn('row', call_args[1]['json']['filters'])
        self.assertIn('col', call_args[1]['json']['filters'])
        self.assertEqual(len(call_args[1]['json']['filters']['row']), 3)
        self.assertEqual(len(call_args[1]['json']['filters']['col']), 3)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_upload_all_future_grids(self, mock_post):
        """Test uploading all future grids with --all-future flag."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--all-future', 
                    '--api-url', 'http://test.com', '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        
        # Should upload today, tomorrow, and day after (3 grids)
        self.assertIn('Total grids: 3', output)
        self.assertIn('Successful: 3', output)
        
        # Verify API was called 3 times
        self.assertEqual(mock_post.call_count, 3)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_dry_run_mode(self, mock_post):
        """Test dry run mode doesn't make actual API calls."""
        out = StringIO()
        call_command('upload_grids_to_production', '--dry-run', 
                    '--api-url', 'http://test.com', '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        
        # Verify dry run output
        self.assertIn('[DRY RUN]', output)
        self.assertIn('Dry run: True', output)
        
        # Verify no actual API calls were made
        mock_post.assert_not_called()

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_force_flag_included_in_payload(self, mock_post):
        """Test that --force flag is included in the API payload."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--force', 
                    '--api-url', 'http://test.com', '--api-key', 'testkey', stdout=out)
        
        # Verify force flag is in the payload
        call_args = mock_post.call_args
        self.assertTrue(call_args[1]['json']['force'])

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_api_error_handling(self, mock_post):
        """Test handling of API errors."""
        # Mock an error response
        mock_post.return_value = self._create_mock_response(
            status_code=400,
            json_data={'status': 'error', 'message': 'Grid already exists'}
        )
        
        out = StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                        '--api-key', 'testkey', stdout=out)
        
        # Verify it exits with error code
        self.assertEqual(cm.exception.code, 1)
        
        output = out.getvalue()
        self.assertIn('Failed to upload', output)
        self.assertIn('Grid already exists', output)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_network_error_handling(self, mock_post):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError('Network error')
        
        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                        '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Network error', output)

    def test_no_grid_for_today(self):
        """Test command when no grid exists for today."""
        # Delete today's grid
        GameFilterDB.objects.filter(date=self.today).delete()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                    '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No grid found for today', output)

    def test_incomplete_grid_handling(self):
        """Test handling of incomplete grids (missing filters)."""
        # Delete one filter to make the grid incomplete
        GameFilterDB.objects.filter(date=self.today, filter_index=2).delete()
        
        out = StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                        '--api-key', 'testkey', stdout=out)
        
        # Verify it exits with error code
        self.assertEqual(cm.exception.code, 1)
        
        output = out.getvalue()
        self.assertIn('incomplete filters', output)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_filters_correctly_mapped(self, mock_post):
        """Test that static filters map to 'row' and dynamic filters map to 'col'."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                    '--api-key', 'testkey', stdout=out)
        
        # Get the payload
        call_args = mock_post.call_args
        filters = call_args[1]['json']['filters']
        
        # Verify row filters (static)
        self.assertEqual(len(filters['row']), 3)
        for i in range(3):
            self.assertIn(str(i), filters['row'])
            self.assertEqual(filters['row'][str(i)]['class'], 'TeamFilter')
            self.assertIn('team_name', filters['row'][str(i)]['config'])
        
        # Verify col filters (dynamic)
        self.assertEqual(len(filters['col']), 3)
        for i in range(3):
            self.assertIn(str(i), filters['col'])
            self.assertEqual(filters['col'][str(i)]['class'], 'DynamicGameFilter')

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_game_title_included(self, mock_post):
        """Test that game title from metadata is included in the upload."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                    '--api-key', 'testkey', stdout=out)
        
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['game_title'], f'Test Grid for {self.today}')

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_api_headers_set_correctly(self, mock_post):
        """Test that API headers are set correctly."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--api-url', 'http://test.com', 
                    '--api-key', 'myspecialkey', stdout=out)
        
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        self.assertEqual(headers['X-API-Key'], 'myspecialkey')
        self.assertEqual(headers['Content-Type'], 'application/json')

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_date_range_displayed(self, mock_post):
        """Test that date range is displayed in output."""
        mock_post.return_value = self._create_mock_response()
        
        out = StringIO()
        call_command('upload_grids_to_production', '--all-future', 
                    '--api-url', 'http://test.com', '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        self.assertIn(f'Date range: {self.today} to {self.day_after}', output)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_environment_variables_for_api_config(self, mock_post):
        """Test that environment variables are used for API configuration."""
        mock_post.return_value = self._create_mock_response()
        
        # The command should use default values if no args provided
        with patch.dict('os.environ', {'NBAGRID_API_URL': 'http://env-url.com', 
                                        'NBAGRID_API_KEY': 'env-key'}):
            out = StringIO()
            call_command('upload_grids_to_production', stdout=out)
            
            # Verify the env URL is displayed
            output = out.getvalue()
            self.assertIn('http://env-url.com', output)

    @patch('nbagrid_api_app.management.commands.upload_grids_to_production.requests.post')
    def test_mixed_success_and_failure(self, mock_post):
        """Test handling of mixed success and failure responses."""
        # First call succeeds, second fails, third succeeds
        mock_post.side_effect = [
            self._create_mock_response(200, {'status': 'success', 'message': 'OK'}),
            self._create_mock_response(400, {'status': 'error', 'message': 'Error'}),
            self._create_mock_response(200, {'status': 'success', 'message': 'OK'}),
        ]
        
        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command('upload_grids_to_production', '--all-future', 
                        '--api-url', 'http://test.com', '--api-key', 'testkey', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Total grids: 3', output)
        self.assertIn('Successful: 2', output)
        self.assertIn('Failed: 1', output)

