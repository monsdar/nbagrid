from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from ..models import Player, GameResult

class GameResultTests(TestCase):
    def setUp(self):
        """Set up test data for each test case."""
        self.today = timezone.now().date()
        self.yesterday = self.today - timedelta(days=1)
        
    def test_initialize_scores_from_recent_games(self):
        """Test the new ranking-based initialization of scores."""
        # Create test players
        players = []
        for i in range(9):  # Create 9 players
            player = Player.objects.create(
                stats_id=i,
                name=f"Player{i}",
                display_name=f"Player{i}"
            )
            players.append(player)
        
        # Create some historical game results to establish pick counts
        # Player0: 10 picks (most picked)
        # Player1: 8 picks
        # Player2: 6 picks
        # Player3: 4 picks
        # Player4: 2 picks
        # Player5: 0 picks
        # Player6-8: 0 picks (bottom third)
        pick_counts = [10, 8, 6, 4, 2, 0, 0, 0, 0]
        for i, player in enumerate(players):
            for j in range(pick_counts[i]):
                GameResult.objects.create(
                    date=self.yesterday - timedelta(days=j),
                    cell_key="0_0",
                    player=player,
                    guess_count=1
                )
        
        # Initialize scores for today
        game_factor = 5
        GameResult.initialize_scores_from_recent_games(
            date=self.today,
            cell_key="0_0",
            game_factor=game_factor
        )
        
        # Get all results for today
        results = GameResult.objects.filter(
            date=self.today,
            cell_key="0_0"
        ).order_by('-guess_count')
        
        # Verify results
        self.assertEqual(len(results), 9)  # All 9 players should have entries
        
        # Top 6 players should have non-zero scores
        # Bottom 3 players should have zero scores
        expected_counts = [
            (players[0], 45),  # (9-1+1)*5 = 45
            (players[1], 40),  # (9-2+1)*5 = 40
            (players[2], 35),  # (9-3+1)*5 = 35
            (players[3], 30),  # (9-4+1)*5 = 30
            (players[4], 25),  # (9-5+1)*5 = 25
            (players[5], 0),   # No picks
            (players[6], 0),   # Bottom third
            (players[7], 0),   # Bottom third
            (players[8], 0),   # Bottom third
        ]
        
        for result, (player, expected_count) in zip(results, expected_counts):
            self.assertEqual(result.player, player)
            self.assertEqual(result.guess_count, expected_count)

    def test_initialize_scores_with_filters(self):
        """Test initialization with filters applied."""
        # Create test players with different positions
        players = []
        positions = ['PG', 'SG', 'SF', 'PF', 'C']
        for i in range(5):
            player = Player.objects.create(
                stats_id=i,
                name=f"Player{i}",
                display_name=f"Player{i}",
                position=positions[i]
            )
            players.append(player)
        
        # Create some historical picks
        for i, player in enumerate(players):
            GameResult.objects.create(
                date=self.yesterday,
                cell_key="0_0",
                player=player,
                guess_count=i+1  # Player0: 1 pick, Player1: 2 picks, etc.
            )
        
        # Create a simple position filter
        class PositionFilter:
            def __init__(self, position):
                self.position = position
                
            def apply_filter(self, queryset):
                return queryset.filter(position=self.position)
                
            def get_desc(self):
                return f"Position: {self.position}"
        
        # Initialize scores with a position filter
        GameResult.initialize_scores_from_recent_games(
            date=self.today,
            cell_key="0_0",
            game_factor=5,
            filters=[PositionFilter('PG')]
        )
        
        # Verify only PG players have entries
        results = GameResult.objects.filter(
            date=self.today,
            cell_key="0_0"
        )
        
        self.assertEqual(results.count(), 1)  # Only one PG player
        self.assertEqual(results.first().player, players[0])  # Player0 is PG
        self.assertEqual(results.first().guess_count, 0)  # guess_count 0, because only the PG is picked and this is in the bottom third