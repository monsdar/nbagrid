from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from ..models import GameCompletion

class GameCompletionTests(TestCase):
    def setUp(self):
        """Set up test data for each test case."""
        self.today = timezone.now().date()
        self.yesterday = self.today - timedelta(days=1)
        self.two_days_ago = self.today - timedelta(days=2)
        
        # Create test session keys
        self.session1 = "session1"
        self.session2 = "session2"
        self.session3 = "session3"
        
        # Create some test completions
        # Session 1: 3-day streak
        GameCompletion.objects.create(
            date=self.two_days_ago,
            session_key=self.session1,
            correct_cells=9,
            final_score=8.5,
            completion_streak=1,
            perfect_streak=1
        )
        GameCompletion.objects.create(
            date=self.yesterday,
            session_key=self.session1,
            correct_cells=9,
            final_score=8.7,
            completion_streak=2,
            perfect_streak=2
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session1,
            correct_cells=9,
            final_score=8.9,
            completion_streak=3,
            perfect_streak=3
        )
        
        # Session 2: 2-day streak
        GameCompletion.objects.create(
            date=self.yesterday,
            session_key=self.session2,
            correct_cells=9,
            final_score=8.0,
            completion_streak=1,
            perfect_streak=1
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session2,
            correct_cells=9,
            final_score=8.2,
            completion_streak=2,
            perfect_streak=2
        )
        
        # Session 3: 1-day streak (just today)
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session3,
            correct_cells=9,
            final_score=7.5,
            completion_streak=1,
            perfect_streak=1
        )

    def test_get_current_streak_single_player(self):
        """Test streak ranking when there's only one player with a streak."""
        # Delete all completions except for session1
        GameCompletion.objects.exclude(session_key=self.session1).delete()
        
        streak, rank, total = GameCompletion.get_current_streak(self.session1, self.today)
        self.assertEqual(streak, 3)  # 3-day streak
        self.assertEqual(rank, 1)    # Rank 1
        self.assertEqual(total, 1)   # Only one player

    def test_get_current_streak_multiple_players(self):
        """Test streak ranking with multiple players having different streaks."""
        streak, rank, total = GameCompletion.get_current_streak(self.session1, self.today)
        self.assertEqual(streak, 3)  # 3-day streak
        self.assertEqual(rank, 1)    # Rank 1 (highest streak)
        self.assertEqual(total, 3)   # Three players total
        
        streak, rank, total = GameCompletion.get_current_streak(self.session2, self.today)
        self.assertEqual(streak, 2)  # 2-day streak
        self.assertEqual(rank, 2)    # Rank 2
        self.assertEqual(total, 3)   # Three players total
        
        streak, rank, total = GameCompletion.get_current_streak(self.session3, self.today)
        self.assertEqual(streak, 1)  # 1-day streak
        self.assertEqual(rank, 3)    # Rank 3
        self.assertEqual(total, 3)   # Three players total

    def test_get_current_streak_no_streak(self):
        """Test streak ranking when the player has no streak."""
        # Create a new session with no completions
        new_session = "new_session"
        streak, rank, total = GameCompletion.get_current_streak(new_session, self.today)
        self.assertEqual(streak, 0)  # No streak
        self.assertEqual(rank, 0)    # No rank
        self.assertEqual(total, 0)   # Not counted in total

    def test_get_current_streak_tied_streaks(self):
        """Test streak ranking when multiple players have the same streak."""
        # Modify session2 to have the same streak as session1
        completion = GameCompletion.objects.get(session_key=self.session2, date=self.today)
        completion.completion_streak = 3
        completion.save()
        
        # Both players should be rank 1
        streak1, rank1, total = GameCompletion.get_current_streak(self.session1, self.today)
        streak2, rank2, total = GameCompletion.get_current_streak(self.session2, self.today)
        
        self.assertEqual(streak1, 3)
        self.assertEqual(streak2, 3)
        self.assertEqual(rank1, 1)
        self.assertEqual(rank2, 1)
        self.assertEqual(total, 3)