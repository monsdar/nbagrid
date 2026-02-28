"""Tests for the sync_to_production management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from nbagrid_api_app.models import Player, Team


class SyncToProductionCommandTests(TestCase):
    """Test cases for sync_to_production management command."""

    def setUp(self):
        """Set up test data."""
        # Create test teams
        self.team1 = Team.objects.create(stats_id=1, name="Team One", abbr="TO1")
        self.team2 = Team.objects.create(stats_id=2, name="Team Two", abbr="TO2")
        self.team3 = Team.objects.create(stats_id=3, name="Team Three", abbr="TO3")

        # Create test player with multiple teams (simulating a trade)
        self.player1 = Player.objects.create(
            stats_id=101,
            name="Test Player",
            last_name="Player",
            display_name="Test Player",
            is_active=True,
        )
        self.player1.teams.add(self.team1, self.team2)

        # Create another player
        self.player2 = Player.objects.create(
            stats_id=102,
            name="Another Player",
            last_name="Player",
            display_name="Another Player",
            is_active=True,
        )
        self.player2.teams.add(self.team3)

        # Create inactive player
        self.inactive_player = Player.objects.create(
            stats_id=103,
            name="Inactive Player",
            last_name="Player",
            display_name="Inactive Player",
            is_active=False,
        )
        self.inactive_player.teams.add(self.team1)

    def tearDown(self):
        """Clean up test data."""
        Player.objects.all().delete()
        Team.objects.all().delete()

    def _create_mock_response(self, status_code=200):
        """Helper to create a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        
        if status_code == 200:
            mock_response.raise_for_status = MagicMock()
        else:
            from requests.exceptions import HTTPError
            mock_response.raise_for_status = MagicMock(side_effect=HTTPError())
        
        return mock_response

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_player_teams_synced_via_relationships(self, mock_session_cls):
        """Test that player teams are synced via relationship endpoints."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--player-ids', '101',
            '--player-teams',
            stdout=out
        )

        # Player 101 has 2 teams, so we should have 2 relationship endpoint calls
        self.assertEqual(mock_session.post.call_count, 2)
        
        # Verify the relationship endpoints were called
        called_urls = [call[0][0] for call in mock_session.post.call_args_list]
        self.assertIn('http://test.com/player/101/team/1', called_urls)
        self.assertIn('http://test.com/player/101/team/2', called_urls)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_sync_players_includes_all_players(self, mock_session_cls):
        """Test that all players (including inactive) are synced by default."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--players',
            stdout=out
        )

        output = out.getvalue()

        # Should sync all 3 players
        self.assertIn('3 successful', output)
        self.assertEqual(mock_session.post.call_count, 3)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_sync_teams_successful(self, mock_session_cls):
        """Test syncing teams to production."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--teams',
            stdout=out
        )

        output = out.getvalue()

        # Should sync all 3 teams
        self.assertIn('3 successful', output)
        self.assertEqual(mock_session.post.call_count, 3)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_sync_player_teams_relationships(self, mock_session_cls):
        """Test syncing player-team relationships."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--player-teams',
            stdout=out
        )

        output = out.getvalue()

        # Should only sync active players' relationships (player1 and player2)
        # player1 has 2 teams, player2 has 1 team = 3 relationships
        self.assertIn('3 successful', output)
        self.assertEqual(mock_session.post.call_count, 3)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_sync_specific_player_by_id(self, mock_session_cls):
        """Test syncing a specific player by ID."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--players',
            '--player-ids', '101',
            stdout=out
        )

        output = out.getvalue()

        # Should only sync player1
        self.assertIn('1 successful', output)
        self.assertEqual(mock_session.post.call_count, 1)

        # Verify the correct player was synced
        json_data = mock_session.post.call_args[1]['json']
        self.assertEqual(json_data['stats_id'], 101)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_dry_run_mode(self, mock_session_cls):
        """Test dry run mode doesn't make actual API calls."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--players',
            '--dry-run',
            stdout=out
        )

        output = out.getvalue()

        # Verify dry run output
        self.assertIn('DRY RUN', output)

        # Verify no actual API calls were made
        mock_session.post.assert_not_called()

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_api_error_handling(self, mock_session_cls):
        """Test handling of API errors."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response(status_code=500)

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--players',
            stdout=out
        )

        output = out.getvalue()
        # Should have failed syncs reported
        self.assertIn('error', output.lower())

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_sync_all_flag(self, mock_session_cls):
        """Test --all flag syncs players, teams, and relationships."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--all',
            stdout=out
        )

        output = out.getvalue()

        # Should sync teams (3), players (3), and relationships (3) = 9 total calls
        self.assertEqual(mock_session.post.call_count, 9)
        self.assertIn('Teams sync completed', output)
        self.assertIn('Players sync completed', output)
        self.assertIn('Relationships sync completed', output)

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_serialize_player_includes_teammates(self, mock_session_cls):
        """Test that player serialization includes teammates field."""
        # Add a teammate relationship
        self.player1.teammates.add(self.player2)

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--player-ids', '101',
            '--players',
            stdout=out
        )

        # Get the serialized data for player1
        json_data = mock_session.post.call_args[1]['json']

        # Assert teammates field is present and contains correct stats_ids
        self.assertIn('teammates', json_data, "Player data should include 'teammates' field")
        self.assertIsInstance(json_data['teammates'], list, "Teammates should be a list")
        self.assertIn(102, json_data['teammates'], "Player should have teammate with stats_id 102")

    @patch('nbagrid_api_app.management.commands.sync_to_production.requests.Session')
    def test_player_traded_to_new_team(self, mock_session_cls):
        """Test that when a player is traded, the new team relationship is synced."""
        # Simulate Dennis Schroder trade scenario:
        # Player was on team1 and team2, now also on team3 (traded)
        self.player1.teams.add(self.team3)

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._create_mock_response()

        out = StringIO()
        call_command(
            'sync_to_production',
            '--production-url', 'http://test.com',
            '--api-key', 'testkey',
            '--player-ids', '101',
            '--player-teams',
            stdout=out
        )

        # Player now has 3 teams, so we should have 3 relationship endpoint calls
        self.assertEqual(mock_session.post.call_count, 3, "Should sync all 3 team relationships")
        
        # Verify all team relationships were synced
        called_urls = [call[0][0] for call in mock_session.post.call_args_list]
        self.assertIn('http://test.com/player/101/team/1', called_urls)
        self.assertIn('http://test.com/player/101/team/2', called_urls)
        self.assertIn('http://test.com/player/101/team/3', called_urls, "New team relationship should be synced")
