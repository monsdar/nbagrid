from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from nbagrid_api_app.models import Player, GameResult
from nbagrid_api_app.GameFilter import GameFilter
from unittest.mock import patch
from django.conf import settings

class MockFilter(GameFilter):
    def __init__(self, filter_field=None, filter_value=None, description=None):
        self.filter_field = filter_field
        self.filter_value = filter_value
        self.description = description or "Mock Filter"
    
    def get_desc(self):
        return self.description
    
    def apply_filter(self, queryset):
        if self.filter_field and self.filter_value is not None:
            return queryset.filter(**{self.filter_field: self.filter_value})
        return queryset.none()  # Return empty queryset by default
    
    def __iter__(self):
        yield self

class GameViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Use a fixed date for testing
        self.test_date = datetime(2025, 5, 1)
        self.url = reverse('game', kwargs={
            'year': self.test_date.year,
            'month': self.test_date.month,
            'day': self.test_date.day
        })
        
        # Create test player with specific attributes for filter testing
        self.player = Player.objects.create(
            stats_id=1,
            name="Test Player",
            position="Guard",
            country="USA",
            career_ppg=20,
            career_rpg=6,
            career_apg=4,
            career_gp=200
        )
        
        # Create mock filters with actual filtering criteria
        self.mock_static_filters = [
            MockFilter(filter_field='position', filter_value='Guard', description='Plays Guard position'),
            MockFilter(filter_field='country', filter_value='USA', description='US Player'),
            MockFilter(filter_field='career_ppg__gte', filter_value=15, description='Career PPG: 15+')
        ]
        
        self.mock_dynamic_filters = [
            MockFilter(filter_field='career_rpg__gte', filter_value=5, description='Career RPG: 5+'),
            MockFilter(filter_field='career_apg__gte', filter_value=3, description='Career APG: 3+'),
            MockFilter(filter_field='career_gp__gte', filter_value=100, description='Career GP: 100+')
        ]
        
        # Setup GameBuilder mock
        self.game_builder_patcher = patch('nbagrid_api_app.views.GameBuilder')
        self.mock_game_builder = self.game_builder_patcher.start()
        self.mock_game_builder.return_value.get_tuned_filters.return_value = (
            self.mock_static_filters,
            self.mock_dynamic_filters
        )
        
        # Setup datetime mock
        self.datetime_patcher = patch('nbagrid_api_app.views.datetime')
        self.mock_datetime = self.datetime_patcher.start()
        self.mock_datetime.now.return_value = self.test_date
        self.mock_datetime.datetime = datetime
        self.mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        
        # Setup build_grid mock
        self.build_grid_patcher = patch('nbagrid_api_app.views.build_grid')
        self.mock_build_grid = self.build_grid_patcher.start()
        self.mock_build_grid.return_value = [
            [{'filters': [self.mock_static_filters[0], self.mock_dynamic_filters[0]], 'row': 0, 'col': 0},
             {'filters': [self.mock_static_filters[1], self.mock_dynamic_filters[0]], 'row': 0, 'col': 1},
             {'filters': [self.mock_static_filters[2], self.mock_dynamic_filters[0]], 'row': 0, 'col': 2}],
            [{'filters': [self.mock_static_filters[0], self.mock_dynamic_filters[1]], 'row': 1, 'col': 0},
             {'filters': [self.mock_static_filters[1], self.mock_dynamic_filters[1]], 'row': 1, 'col': 1},
             {'filters': [self.mock_static_filters[2], self.mock_dynamic_filters[1]], 'row': 1, 'col': 2}],
            [{'filters': [self.mock_static_filters[0], self.mock_dynamic_filters[2]], 'row': 2, 'col': 0},
             {'filters': [self.mock_static_filters[1], self.mock_dynamic_filters[2]], 'row': 2, 'col': 1},
             {'filters': [self.mock_static_filters[2], self.mock_dynamic_filters[2]], 'row': 2, 'col': 2}]
        ]
        
        # Initialize session
        session = self.client.session
        self.game_state_key = f'game_state_{self.test_date.year}_{self.test_date.month}_{self.test_date.day}'
        session[self.game_state_key] = {
            'attempts_remaining': 10,
            'selected_cells': {},
            'is_finished': False
        }
        session.save()
        
    def tearDown(self):
        self.game_builder_patcher.stop()
        self.datetime_patcher.stop()
        self.build_grid_patcher.stop()

    def test_get_game_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game.html')

    def test_invalid_date_redirect(self):
        # Test future date redirect
        future_date = self.test_date + timedelta(days=1)
        url = reverse('game', kwargs={
            'year': future_date.year,
            'month': future_date.month,
            'day': future_date.day
        })
        response = self.client.get(url)
        self.assertRedirects(response, self.url)

        # Test past date before April 1st 2025
        past_date = datetime(2024, 3, 31)
        url = reverse('game', kwargs={
            'year': past_date.year,
            'month': past_date.month,
            'day': past_date.day
        })
        response = self.client.get(url)
        self.assertRedirects(response, self.url)

    def test_game_state_initialization(self):
        # Clear the session first
        session = self.client.session
        session.clear()
        session.save()
        
        # Make the request
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        
        # Get the new session
        session = self.client.session
        game_state_key = f'game_state_{self.test_date.year}_{self.test_date.month}_{self.test_date.day}'
        
        self.assertIn(game_state_key, session)
        game_state = session[game_state_key]
        self.assertEqual(game_state['attempts_remaining'], 10)
        self.assertEqual(game_state['selected_cells'], {})
        self.assertFalse(game_state['is_finished'])

    def test_player_guess_handling(self):
        # Make a guess - this should work because our test player matches the filter criteria
        response = self.client.post(self.url, {
            'player_id': self.player.stats_id,
            'row': 0,
            'col': 0
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_correct'])
        self.assertEqual(data['attempts_remaining'], 9)
        self.assertFalse(data['is_finished'])

    def test_game_completion(self):
        """Test that game completion is handled correctly"""
        # Initialize game state with one attempt left
        session = self.client.session
        session[self.game_state_key] = {
            'attempts_remaining': 1,
            'selected_cells': {},
            'is_finished': False
        }
        session.save()
        
        # Make a guess that should finish the game
        response = self.client.post(self.url, {
            'player_id': self.player.stats_id,
            'row': 0,
            'col': 0
        })
        
        # Check that the game is marked as finished
        self.assertEqual(response.status_code, 200)
        game_state = self.client.session.get(self.game_state_key)
        self.assertTrue(game_state['is_finished'])
        self.assertEqual(game_state['attempts_remaining'], 0)
        
        # Check that the response contains the correct game state
        data = response.json()
        self.assertTrue(data['is_finished'])
        self.assertEqual(data['attempts_remaining'], 0)
        cell_data = data['selected_cells'][f'0_0'][0]  # Get the first (and only) cell data
        self.assertEqual(cell_data['player_id'], str(self.player.stats_id))

    def test_game_completion_all_cells_correct(self):
        # Initialize game state with all cells correct but attempts remaining
        session = self.client.session
        session[self.game_state_key] = {
            'attempts_remaining': 5,  # Still have attempts left
            'selected_cells': {
                '0_0': [{'is_correct': False}],  # we post a positive guess for this cell later in the test
                '0_1': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '0_2': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '1_0': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '1_1': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '1_2': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '2_0': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '2_1': [{'is_correct': True, 'player_id': self.player.stats_id}],
                '2_2': [{'is_correct': True, 'player_id': self.player.stats_id}]
            },
            'is_finished': False
        }
        session.save()

        # Make a guess - should mark game as finished since all cells will be correct
        response = self.client.post(self.url, {
            'player_id': self.player.stats_id,
            'row': 0,
            'col': 0
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_finished'])
        self.assertEqual(data['attempts_remaining'], 4)  # Should still have attempts left

    @patch('nbagrid_api_app.models.GameResult.get_player_rarity_score')
    def test_score_calculation(self, mock_get_score):
        mock_get_score.return_value = 0.5
        
        # Create a game result for score calculation
        GameResult.objects.create(
            date=self.test_date.date(),
            cell_key='0_0',
            player=self.player,
            guess_count=1
        )

        # Initialize game state with a correct guess
        session = self.client.session
        session[self.game_state_key] = {
            'attempts_remaining': 10,
            'selected_cells': {
                '0_0': [{
                    'player_id': str(self.player.stats_id),
                    'player_name': self.player.name,
                    'is_correct': True,
                    'score': 0.5
                }]
            },
            'is_finished': False,
            'total_score': 0.5
        }
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_score', response.context)
        self.assertEqual(response.context['total_score'], 0.5)

class PlayerUpdateTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a test player
        self.player = Player.objects.create(
            stats_id=1,
            name="Test Player",
            position="Guard",
            country="USA",
            career_ppg=20.0,
            career_rpg=6.0,
            career_apg=4.0,
            career_gp=200
        )
        # Get the API key from settings
        self.api_key = settings.NBAGRID_API_KEY
    
    def test_update_player_success(self):
        # Test updating multiple fields
        response = self.client.post(
            f"/api/player/{self.player.stats_id}",
            {
                "name": "Updated Player",
                "display_name": "Updated Player Display",
                "position": "Forward",
                "career_ppg": 25.0,
                "is_award_mvp": True,
            },
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("updated", data["message"].lower())
        
        # Verify the updates
        updated_player = Player.objects.get(stats_id=self.player.stats_id)
        self.assertEqual(updated_player.name, "Updated Player")
        self.assertEqual(updated_player.display_name, "Updated Player Display")
        self.assertEqual(updated_player.position, "Forward")
        self.assertEqual(updated_player.career_ppg, 25.0)
        self.assertTrue(updated_player.is_award_mvp)
    
    def test_create_new_player(self):
        # Test creating a new player
        response = self.client.post(
            "/api/player/999",
            {
                "name": "New Player",
                "display_name": "New Player Display",
                "position": "Center",
                "career_ppg": 15.0,
            },
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("created", data["message"].lower())
        
        # Verify the new player was created
        new_player = Player.objects.get(stats_id=999)
        self.assertEqual(new_player.name, "New Player")
        self.assertEqual(new_player.display_name, "New Player Display")
        self.assertEqual(new_player.position, "Center")
        self.assertEqual(new_player.career_ppg, 15.0)
    
    def test_create_player_with_minimal_data(self):
        # Test creating a player with just stats_id and required fields
        response = self.client.post(
            "/api/player/1000",
            {
                "name": "Minimal Player",
            },
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("created", data["message"].lower())
        
        # Verify the player was created with minimal data
        new_player = Player.objects.get(stats_id=1000)
        self.assertEqual(new_player.name, "Minimal Player")
    
    def test_update_player_invalid_data(self):
        response = self.client.post(
            f"/api/player/{self.player.stats_id}",
            {
                "name": "Invalid Player",
                "career_ppg": "invalid",  # Invalid type for career_ppg
            },
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key
        )
        
        self.assertEqual(response.status_code, 422)
        