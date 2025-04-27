from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from nbagrid_api_app.models import Player, GameResult
from nbagrid_api_app.GameFilter import GameFilter
from unittest.mock import patch, MagicMock

class MockFilter(GameFilter):
    def __init__(self):
        self.desc = "Mock Filter"
    
    def get_desc(self):
        return self.desc
    
    def apply_filter(self, queryset):
        return queryset

class GameViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Use a fixed date for testing
        self.test_date = datetime(2025, 4, 1)
        self.url = reverse('game', kwargs={
            'year': self.test_date.year,
            'month': self.test_date.month,
            'day': self.test_date.day
        })
        
        # Create test player
        self.player = Player.objects.create(
            stats_id=1,
            name="Test Player"
        )
        
        # Create mock filters
        self.mock_static_filters = [MockFilter() for _ in range(3)]
        self.mock_dynamic_filters = [MockFilter() for _ in range(3)]
        
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
        mock_now = MagicMock()
        mock_now.return_value = self.test_date
        self.mock_datetime.now = mock_now
        self.mock_datetime.datetime = datetime
        self.mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
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
        
        # Debug output
        print(f"\nSession keys: {session.keys()}")
        print(f"Looking for key: {game_state_key}")
        print(f"Session contents: {dict(session)}")
        
        self.assertIn(game_state_key, session)
        game_state = session[game_state_key]
        self.assertEqual(game_state['attempts_remaining'], 10)
        self.assertEqual(game_state['selected_cells'], {})
        self.assertFalse(game_state['is_finished'])

    @patch('nbagrid_api_app.views.Player.objects.filter')
    def test_player_guess_handling(self, mock_filter):
        mock_filter.return_value.exists.return_value = True
        
        # Make a guess
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
        # Initialize game state with one attempt left
        session = self.client.session
        session[self.game_state_key] = {
            'attempts_remaining': 1,
            'selected_cells': {},
            'is_finished': False
        }
        session.save()

        # Make a guess that should finish the game
        with patch('nbagrid_api_app.views.Player.objects.filter') as mock_filter:
            mock_filter.return_value.exists.return_value = True
            response = self.client.post(self.url, {
                'player_id': self.player.stats_id,
                'row': 0,
                'col': 0
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['is_finished'])
            self.assertEqual(data['attempts_remaining'], 0)

    def test_game_completion_all_cells_correct(self):
        # Initialize game state with all cells correct but attempts remaining
        session = self.client.session
        session[self.game_state_key] = {
            'attempts_remaining': 5,  # Still have attempts left
            'selected_cells': {
                '0_0': {'is_correct': False}, # we post a positive guess for this cell later in the test
                '0_1': {'is_correct': True, 'player_id': 1},
                '0_2': {'is_correct': True, 'player_id': 1},
                '1_0': {'is_correct': True, 'player_id': 1},
                '1_1': {'is_correct': True, 'player_id': 1},
                '1_2': {'is_correct': True, 'player_id': 1},
                '2_0': {'is_correct': True, 'player_id': 1},
                '2_1': {'is_correct': True, 'player_id': 1},
                '2_2': {'is_correct': True, 'player_id': 1}
            },
            'is_finished': False
        }
        session.save()

        # Make a guess - should mark game as finished since all cells are correct
        with patch('nbagrid_api_app.views.Player.objects.filter') as mock_filter:
            mock_filter.return_value.exists.return_value = True
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
                '0_0': {
                    'player_id': str(self.player.stats_id),
                    'player_name': self.player.name,
                    'is_correct': True,
                    'score': 0.5
                }
            },
            'is_finished': False,
            'total_score': 0.5
        }
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_score', response.context)
        self.assertEqual(response.context['total_score'], 0.5) 