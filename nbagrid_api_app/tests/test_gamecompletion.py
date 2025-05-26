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

    def test_get_ranking_with_neighbors(self):
        """Test the ranking with neighbors functionality."""
        from ..models import UserData
        
        # Create UserData entries for our test sessions
        UserData.objects.create(session_key=self.session1, display_name="Player1") # Highest score, 20
        UserData.objects.create(session_key=self.session2, display_name="Player2") # 15
        UserData.objects.create(session_key=self.session3, display_name="Player3") # 10
        
        # Create additional test data with different scores
        session4 = "session4"
        session5 = "session5"
        session6 = "session6"
        session7 = "session7"
        
        UserData.objects.create(session_key=session4, display_name="Player4") # 9
        UserData.objects.create(session_key=session5, display_name="Player5") # 8
        UserData.objects.create(session_key=session6, display_name="Player6") # 7
        UserData.objects.create(session_key=session7, display_name="Player7") # Lowest Score, 6
        
        GameCompletion.objects.filter(date=self.today).delete()
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session1,
            correct_cells=9,
            final_score=20, # Highest score
            completion_streak=3,
            perfect_streak=3
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session2,
            correct_cells=9,
            final_score=15,
            completion_streak=2,
            perfect_streak=2
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=self.session3,
            correct_cells=9,
            final_score=10,
            completion_streak=1,
            perfect_streak=1
        )
        
        # Create completions with different scores
        GameCompletion.objects.create(
            date=self.today,
            session_key=session4,
            correct_cells=9,
            final_score=9.0,
            completion_streak=1,
            perfect_streak=1
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=session5,
            correct_cells=9,
            final_score=8.0,
            completion_streak=1,
            perfect_streak=1
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=session6,
            correct_cells=9,
            final_score=7.0,
            completion_streak=1,
            perfect_streak=1
        )
        GameCompletion.objects.create(
            date=self.today,
            session_key=session7,
            correct_cells=9,
            final_score=6.0,  # Lowest score
            completion_streak=1,
            perfect_streak=1
        )
        
        # Test case 1: Current user in middle of ranking
        ranking = GameCompletion.get_ranking_with_neighbors(self.today, session4)
        self.assertEqual(len(ranking), 5)  # Should show 5 entries
        self.assertEqual(ranking[0][1], "Player2")  # Highest score
        self.assertEqual(ranking[1][1], "Player3")
        self.assertEqual(ranking[2][1], "Player4")  # Current user
        self.assertEqual(ranking[3][1], "Player5")
        self.assertEqual(ranking[4][1], "Player6")
        
        # Test case 2: Current user at top of ranking
        ranking = GameCompletion.get_ranking_with_neighbors(self.today, self.session1)
        self.assertEqual(len(ranking), 5)
        self.assertEqual(ranking[0][1], "Player1")  # Current user
        self.assertEqual(ranking[1][1], "Player2")
        self.assertEqual(ranking[2][1], "Player3")
        self.assertEqual(ranking[3][1], "Player4")
        self.assertEqual(ranking[4][1], "Player5")
        
        # Test case 3: Current user at bottom of ranking
        ranking = GameCompletion.get_ranking_with_neighbors(self.today, session7)
        self.assertEqual(len(ranking), 5)
        self.assertEqual(ranking[0][1], "Player3")
        self.assertEqual(ranking[1][1], "Player4")
        self.assertEqual(ranking[2][1], "Player5")
        self.assertEqual(ranking[3][1], "Player6")
        self.assertEqual(ranking[4][1], "Player7")  # Current user
        
        # Test case 4: Current user near bottom of ranking
        ranking = GameCompletion.get_ranking_with_neighbors(self.today, session6)
        self.assertEqual(len(ranking), 5)
        self.assertEqual(ranking[0][1], "Player3")
        self.assertEqual(ranking[1][1], "Player4")
        self.assertEqual(ranking[2][1], "Player5")
        self.assertEqual(ranking[3][1], "Player6")   # Current user
        self.assertEqual(ranking[4][1], "Player7")
        
        # Test case 4: Only 1 player in ranking should result in a ranking of 1 entry
        # Delete all completions except for session1
        GameCompletion.objects.exclude(session_key=self.session1).delete()
        
        ranking = GameCompletion.get_ranking_with_neighbors(self.today, self.session1)
        self.assertEqual(len(ranking), 1)  # Should show only 1 entry
        self.assertEqual(ranking[0][1], "Player1")  # Only player
        self.assertEqual(ranking[0][0], 1)  # Rank 1
        self.assertEqual(ranking[0][2], 20)  # Score from setUp
