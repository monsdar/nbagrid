from django.test import TestCase
from nbagrid_api_app.GameState import CellData, GameState
from typing import Dict, Any, List

class TestGameState(TestCase):
    def setUp(self):
        # Create sample cell data
        self.cell_data1: CellData = {
            'player_id': 1,
            'player_name': 'Player One',
            'is_correct': True,
            'tier': 'common',
            'score': 1.0
        }
        self.cell_data2: CellData = {
            'player_id': 2,
            'player_name': 'Player Two',
            'is_correct': False,
            'tier': None,
            'score': 0.0
        }
        self.cell_data3: CellData = {
            'player_id': 3,
            'player_name': 'Player Three',
            'is_correct': True,
            'tier': 'rare',
            'score': 2.0
        }

    def test_cell_data_creation(self):
        """Test that CellData instances are created correctly"""
        self.assertEqual(self.cell_data1['player_id'], 1)
        self.assertEqual(self.cell_data1['player_name'], 'Player One')
        self.assertTrue(self.cell_data1['is_correct'])
        self.assertEqual(self.cell_data1['tier'], 'common')
        self.assertEqual(self.cell_data1['score'], 1.0)

        self.assertEqual(self.cell_data2['player_id'], 2)
        self.assertEqual(self.cell_data2['player_name'], 'Player Two')
        self.assertFalse(self.cell_data2['is_correct'])
        self.assertIsNone(self.cell_data2['tier'])
        self.assertEqual(self.cell_data2['score'], 0.0)

    def test_game_state_initialization(self):
        """Test GameState initialization with default values"""
        game_state = GameState()
        self.assertEqual(game_state.attempts_remaining, 10)
        self.assertEqual(game_state.selected_cells, {})
        self.assertFalse(game_state.is_finished)
        self.assertEqual(game_state.total_score, 0.0)

    def test_game_state_initialization_with_values(self):
        """Test GameState initialization with custom values"""
        selected_cells = {'0_0': [self.cell_data1]}
        game_state = GameState(
            attempts_remaining=5,
            selected_cells=selected_cells,
            is_finished=True,
            total_score=1.0
        )
        self.assertEqual(game_state.attempts_remaining, 5)
        self.assertEqual(game_state.selected_cells, selected_cells)
        self.assertTrue(game_state.is_finished)
        self.assertEqual(game_state.total_score, 1.0)

    def test_from_dict(self):
        """Test creating GameState from dictionary"""
        data: Dict[str, Any] = {
            'attempts_remaining': 5,
            'selected_cells': {
                '0_0': [self.cell_data1],
                '0_1': [self.cell_data2]
            },
            'is_finished': True,
            'total_score': 1.0
        }
        game_state = GameState.from_dict(data)
        self.assertEqual(game_state.attempts_remaining, 5)
        self.assertEqual(len(game_state.selected_cells), 2)
        self.assertTrue(game_state.is_finished)
        self.assertEqual(game_state.total_score, 1.0)

    def test_to_dict(self):
        """Test converting GameState to dictionary"""
        selected_cells = {'0_0': [self.cell_data1]}
        game_state = GameState(
            attempts_remaining=5,
            selected_cells=selected_cells,
            is_finished=True,
            total_score=1.0
        )
        data = game_state.to_dict()
        self.assertEqual(data['attempts_remaining'], 5)
        self.assertEqual(data['selected_cells'], selected_cells)
        self.assertTrue(data['is_finished'])
        self.assertEqual(data['total_score'], 1.0)

    def test_get_cell_data(self):
        """Test getting cell data with defaults"""
        game_state = GameState()
        cell_data_list = game_state.get_cell_data('0_0')
        self.assertEqual(cell_data_list, [])

    def test_add_wrong_guess(self):
        """Test adding wrong guesses"""
        game_state = GameState()
        
        # First wrong guess
        game_state.add_wrong_guess('0_0', 1, 'Player One')
        cell_data_list = game_state.selected_cells['0_0']
        self.assertEqual(len(cell_data_list), 1)
        self.assertEqual(cell_data_list[0]['player_id'], 1)
        self.assertEqual(cell_data_list[0]['player_name'], 'Player One')
        self.assertFalse(cell_data_list[0]['is_correct'])

        # Different player wrong guess
        game_state.add_wrong_guess('0_0', 2, 'Player Two')
        cell_data_list = game_state.selected_cells['0_0']
        self.assertEqual(len(cell_data_list), 2)
        self.assertEqual(cell_data_list[1]['player_id'], 2)
        self.assertEqual(cell_data_list[1]['player_name'], 'Player Two')
        self.assertFalse(cell_data_list[1]['is_correct'])

    def test_add_correct_guess(self):
        """Test setting correct guesses"""
        game_state = GameState()
        game_state.add_correct_guess('0_0', 1, 'Player One', 'common', 1.0)
        cell_data_list = game_state.selected_cells['0_0']
        self.assertEqual(len(cell_data_list), 1)
        self.assertEqual(cell_data_list[0]['player_id'], 1)
        self.assertEqual(cell_data_list[0]['player_name'], 'Player One')
        self.assertTrue(cell_data_list[0]['is_correct'])
        self.assertEqual(cell_data_list[0]['tier'], 'common')
        self.assertEqual(cell_data_list[0]['score'], 1.0)

    def test_decrement_attempts(self):
        """Test decrementing attempts"""
        game_state = GameState(attempts_remaining=3)
        game_state.decrement_attempts()
        self.assertEqual(game_state.attempts_remaining, 2)
        game_state.decrement_attempts()
        self.assertEqual(game_state.attempts_remaining, 1)
        game_state.decrement_attempts()
        self.assertEqual(game_state.attempts_remaining, 0)
        game_state.decrement_attempts()  # Should not go below 0
        self.assertEqual(game_state.attempts_remaining, 0)

    def test_check_completion(self):
        """Test game completion conditions"""
        # Test completion by attempts
        game_state = GameState(attempts_remaining=1)
        self.assertFalse(game_state.is_finished)
        game_state.decrement_attempts()
        self.assertTrue(game_state.check_completion(9))
        self.assertTrue(game_state.is_finished)

        # Test completion by all cells correct
        game_state = GameState(attempts_remaining=10)
        for i in range(9):  # 3x3 grid
            game_state.add_correct_guess(f'{i//3}_{i%3}', i+1, f'Player {i+1}', 'common', 1.0)
        self.assertTrue(game_state.check_completion(9))
        self.assertTrue(game_state.is_finished)

        # Test not completed
        game_state = GameState(attempts_remaining=10)
        self.assertFalse(game_state.check_completion(9))
        self.assertFalse(game_state.is_finished)

    def test_calculate_total_score(self):
        """Test total score calculation"""
        game_state = GameState()
        
        # Add some correct guesses
        game_state.add_correct_guess('0_0', 1, 'Player One', 'common', 1.0)
        game_state.add_correct_guess('0_1', 2, 'Player Two', 'rare', 2.0)
        game_state.add_correct_guess('0_2', 3, 'Player Three', 'common', 1.0)
        
        # Add a wrong guess (should not affect score)
        game_state.add_wrong_guess('1_0', 4, 'Player Four')
        
        total_score = game_state.get_total_score()
        self.assertEqual(total_score, 4.0)
        self.assertEqual(game_state.total_score, 4.0) 