from django.db import models
from django_prometheus.models import ExportModelOperationsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class GameResult(ExportModelOperationsMixin('gameresult'), models.Model):
    """
    Model to track game results and player guesses.
    """
    
    date = models.DateField()
    cell_key = models.CharField(max_length=10)  # e.g., "0_1" for row 0, col 1
    
    # Generic foreign key to any entity type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    entity = GenericForeignKey('content_type', 'object_id')
    
    guess_count = models.IntegerField(default=1)  # Number of times this entity was correctly guessed for this cell
    
    class Meta:
        unique_together = ['date', 'cell_key', 'content_type', 'object_id']
        indexes = [
            models.Index(fields=['date', 'cell_key']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    @classmethod
    def get_cell_stats(cls, date, cell_key):
        """Get statistics for a specific cell on a specific date."""
        return cls.objects.filter(date=date, cell_key=cell_key)
    
    @classmethod
    def get_most_common_entities(cls, date, cell_key, limit=5):
        """Get the most commonly guessed entities for a cell."""
        return cls.objects.filter(date=date, cell_key=cell_key).order_by('-guess_count')[:limit]
    
    @classmethod
    def get_rarest_entities(cls, date, cell_key, limit=5):
        """Get the rarest guessed entities for a cell."""
        return cls.objects.filter(date=date, cell_key=cell_key).order_by('guess_count')[:limit]
    
    @classmethod
    def get_total_guesses(cls, date):
        """Get total number of guesses for a specific date."""
        return cls.objects.filter(date=date).count()
    
    @classmethod
    def get_entity_rarity_score(cls, date, cell_key, entity):
        """Calculate rarity score for an entity in a specific cell."""
        try:
            result = cls.objects.get(
                date=date,
                cell_key=cell_key,
                content_type=ContentType.objects.get_for_model(entity),
                object_id=entity.pk
            )
            return result.guess_count
        except cls.DoesNotExist:
            return 0
    
    @classmethod
    def initialize_scores_from_recent_games(cls, date, cell_key, num_games=5, game_factor=5, filters=None):
        """
        Initialize scores for a cell based on recent games.
        
        Args:
            date: The date for the game
            cell_key: The cell key (e.g., "0_1")
            num_games: Number of recent games to consider
            game_factor: Factor to multiply scores by
            filters: List of filters to apply when finding entities
        """
        # This method will be implemented by domain-specific extensions
        # as it needs to know about the specific entity types and filters
        pass
    
    def __str__(self):
        return f"{self.date} - {self.cell_key} - {self.entity}"


class GameCompletion(ExportModelOperationsMixin('gamecompletion'), models.Model):
    """
    Model to track game completions and user statistics.
    """
    
    date = models.DateField()
    session_key = models.CharField(max_length=40)  # Django session key
    completed_at = models.DateTimeField(auto_now_add=True)
    correct_cells = models.IntegerField(default=0)  # Number of correctly filled cells
    final_score = models.FloatField(default=0.0)    # Final score achieved
    completion_streak = models.IntegerField(default=1)  # Consecutive days of completion
    perfect_streak = models.IntegerField(default=1)  # Consecutive days of perfect completion
    
    class Meta:
        unique_together = ['date', 'session_key']  # Each session can only complete a game once
        indexes = [
            models.Index(fields=['date', 'session_key']),
            models.Index(fields=['session_key', 'date']),
            models.Index(fields=['date', 'correct_cells']),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to calculate streaks."""
        if not self.pk:  # Only on creation
            # Calculate completion streak
            yesterday = self.date - timedelta(days=1)
            try:
                yesterday_completion = GameCompletion.objects.get(
                    date=yesterday,
                    session_key=self.session_key
                )
                self.completion_streak = yesterday_completion.completion_streak + 1
            except GameCompletion.DoesNotExist:
                self.completion_streak = 1
            
            # Calculate perfect streak
            if self.correct_cells == 9:  # Perfect game (3x3 grid)
                try:
                    yesterday_completion = GameCompletion.objects.get(
                        date=yesterday,
                        session_key=self.session_key
                    )
                    if yesterday_completion.correct_cells == 9:
                        self.perfect_streak = yesterday_completion.perfect_streak + 1
                    else:
                        self.perfect_streak = 1
                except GameCompletion.DoesNotExist:
                    self.perfect_streak = 1
            else:
                self.perfect_streak = 0
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_completion_count(cls, date):
        """Get the number of completions for a specific date."""
        return cls.objects.filter(date=date).count()
    
    @classmethod
    def get_average_score(cls, date):
        """Get the average score for a specific date."""
        from django.db.models import Avg
        result = cls.objects.filter(date=date).aggregate(avg_score=Avg('final_score'))
        return result['avg_score'] or 0.0
    
    @classmethod
    def get_average_correct_cells(cls, date):
        """Get the average number of correct cells for a specific date."""
        from django.db.models import Avg
        result = cls.objects.filter(date=date).aggregate(avg_cells=Avg('correct_cells'))
        return result['avg_cells'] or 0.0
    
    @classmethod
    def get_perfect_games(cls, date):
        """Get the number of perfect games for a specific date."""
        return cls.objects.filter(date=date, correct_cells=9).count()
    
    @classmethod
    def get_current_streak(cls, session_key, current_date):
        """Get the current completion streak for a session."""
        try:
            latest_completion = cls.objects.filter(
                session_key=session_key,
                date__lte=current_date
            ).order_by('-date').first()
            
            if not latest_completion:
                return 0, None, 0
            
            # Check if streak is still active (no gaps)
            streak_date = latest_completion.date
            expected_date = current_date
            
            while streak_date <= expected_date:
                try:
                    completion = cls.objects.get(
                        session_key=session_key,
                        date=streak_date
                    )
                    streak_date += timedelta(days=1)
                except cls.DoesNotExist:
                    # Streak broken, calculate from the last completion
                    if latest_completion.date == current_date:
                        return latest_completion.completion_streak, None, 0
                    else:
                        return 0, None, 0
            
            return latest_completion.completion_streak, None, 0
            
        except Exception as e:
            logger.error(f"Error calculating streak for session {session_key}: {e}")
            return 0, None, 0
    
    @classmethod
    def get_top_scores(cls, date, limit=10):
        """Get the top scores for a specific date."""
        return cls.objects.filter(date=date).order_by('-final_score', 'completed_at')[:limit]
    
    @classmethod
    def get_ranking_with_neighbors(cls, date, session_key):
        """Get ranking data with neighboring scores."""
        try:
            user_completion = cls.objects.get(date=date, session_key=session_key)
            
            # Get all completions for this date, ordered by score
            all_completions = list(cls.objects.filter(date=date).order_by('-final_score', 'completed_at'))
            
            # Find user's position
            user_position = None
            for i, completion in enumerate(all_completions):
                if completion.session_key == session_key:
                    user_position = i + 1
                    break
            
            if user_position is None:
                return None
            
            # Get neighboring scores
            neighbors = []
            start_idx = max(0, user_position - 3)  # Show 3 above
            end_idx = min(len(all_completions), user_position + 2)  # Show 2 below
            
            for i in range(start_idx, end_idx):
                completion = all_completions[i]
                neighbors.append({
                    'position': i + 1,
                    'score': completion.final_score,
                    'correct_cells': completion.correct_cells,
                    'is_user': completion.session_key == session_key
                })
            
            return {
                'user_position': user_position,
                'total_players': len(all_completions),
                'neighbors': neighbors
            }
            
        except cls.DoesNotExist:
            return None
    
    def __str__(self):
        return f"{self.date} - {self.session_key} - Score: {self.final_score}"


class GameFilterDB(ExportModelOperationsMixin('gamefilterdb'), models.Model):
    """
    Stores the configuration of game filters for a specific date.
    """
    
    date = models.DateField()
    # TODO: We should modify this to work without the 'static' or 'dynamic' distinction
    filter_type = models.CharField(max_length=10)  # 'static' or 'dynamic'
    filter_class = models.CharField(max_length=50)  # Name of the filter class
    filter_config = models.JSONField()  # Store filter configuration
    filter_row_index = models.IntegerField()  # Position in the grid (0-2 for 3x3 grid)
    filter_col_index = models.IntegerField()  # Position in the grid (0-2 for 3x3 grid)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('date', 'filter_type', 'filter_row_index', 'filter_col_index')
        indexes = [
            models.Index(fields=['date', 'filter_type']),
            models.Index(fields=['filter_class']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.filter_type} - {self.filter_class}"


class UserData(ExportModelOperationsMixin('userdata'), models.Model):
    """
    Model to store user-related data based on their session ID.
    """
    
    session_key = models.CharField(max_length=40, primary_key=True, help_text="Django session key as primary identifier")
    display_name = models.CharField(max_length=14, help_text="Generated display name for the user")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this user data was created")
    last_active = models.DateTimeField(auto_now=True, help_text="When this user was last active")
    
    class Meta:
        indexes = [
            models.Index(fields=['display_name']),
            models.Index(fields=['last_active']),
        ]
    
    @classmethod
    def get_or_create_user(cls, session_key):
        """Get or create user data for a session key."""
        try:
            user_data = cls.objects.get(session_key=session_key)
            # Update last_active
            user_data.save()
            return user_data
        except cls.DoesNotExist:
            # Generate a random display name
            display_name = cls.generate_random_display_name(session_key)
            user_data = cls.objects.create(
                session_key=session_key,
                display_name=display_name
            )
            return user_data
    
    @classmethod
    def generate_random_display_name(cls, session_key):
        """Generate a random display name based on session key."""
        import hashlib
        import random
        
        # Use the session key to generate a deterministic random seed
        seed_hash = int(hashlib.md5(session_key.encode()).hexdigest(), 16)
        random.seed(seed_hash)
        
        # Generate a random adjective + noun combination
        # TODO: Allow for any specific game type to overwrite these lists so that the display name is more specific to the game
        adjectives = ['Swift', 'Bold', 'Quick', 'Bright', 'Sharp', 'Wise', 'Brave', 'Calm', 'Eager', 'Fair']
        nouns = ['Player', 'Gamer', 'Champion', 'Hero', 'Star', 'Legend', 'Master', 'Pro', 'Expert', 'Winner']
        
        adjective = random.choice(adjectives)
        noun = random.choice(nouns)
        display_name = f"{adjective}{noun}"
        
        # Ensure it fits within the 14 character limit
        if len(display_name) > 14:
            display_name = display_name[:14]
        
        return display_name
    
    @classmethod
    def get_display_name(cls, session_key):
        """Get the display name for a session key."""
        try:
            user_data = cls.objects.get(session_key=session_key)
            return user_data.display_name
        except cls.DoesNotExist:
            return None
    
    def __str__(self):
        return f"{self.display_name} ({self.session_key})"


class LastUpdated(ExportModelOperationsMixin('lastupdated'), models.Model):
    """
    Model to track when data was last updated.
    """
    
    data_type = models.CharField(max_length=50, unique=True, help_text="Type of data that was updated")
    last_updated = models.DateTimeField(auto_now=True, help_text="When this data was last updated")
    updated_by = models.CharField(max_length=100, blank=True, null=True, help_text="Who or what performed the update")
    notes = models.TextField(blank=True, null=True, help_text="Additional information about the update")
    
    class Meta:
        indexes = [
            models.Index(fields=['data_type']),
            models.Index(fields=['last_updated']),
        ]
    
    @classmethod
    def update_timestamp(cls, data_type, updated_by=None, notes=None):
        """Update the timestamp for a data type."""
        obj, created = cls.objects.get_or_create(
            data_type=data_type,
            defaults={
                'updated_by': updated_by,
                'notes': notes
            }
        )
        
        if not created:
            obj.updated_by = updated_by
            if notes:
                obj.notes = notes
            obj.save()
        
        return obj
    
    @classmethod
    def get_last_updated(cls, data_type):
        """Get the last updated timestamp for a data type."""
        try:
            obj = cls.objects.get(data_type=data_type)
            return obj.last_updated
        except cls.DoesNotExist:
            return None
    
    def __str__(self):
        return f"{self.data_type} - {self.last_updated}" 