from abc import abstractmethod
from django.db import models
from django_prometheus.models import ExportModelOperationsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class BaseEntity(ExportModelOperationsMixin('base_entity'), models.Model):
    """
    Abstract base model for any entity that can be used in grid games.
    
    This provides the common interface that all game entities must implement.
    """
    
    # Generic fields that most entities will have
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, default="")
    
    # Content type for generic relationships
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        abstract = True
    
    @abstractmethod
    def get_search_terms(self) -> list[str]:
        """
        Return a list of search terms that can be used to find this entity.
        """
        pass
    
    @abstractmethod
    def get_stats_for_filter(self, filter_type: str) -> dict:
        """
        Return statistics relevant to a specific filter type.
        
        Args:
            filter_type: The type of filter requesting stats
            
        Returns:
            Dictionary of statistics relevant to the filter
        """
        pass
    
    def __str__(self):
        return self.display_name or self.name


class BaseGameGrid(ExportModelOperationsMixin('base_game_grid'), models.Model):
    """
    Abstract base model for game grids.
    """
    
    date = models.DateField(unique=True, primary_key=True)
    grid_size = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    game_title = models.CharField(max_length=40, default="")
    domain_name = models.CharField(max_length=50, default="")
    
    # Store the correct entities count for each cell
    cell_correct_entities = models.JSONField(default=dict)
    
    class Meta:
        abstract = True
    
    @property
    def completion_count(self):
        """Get the number of game completions for this grid."""
        from .models import GameCompletion
        return GameCompletion.get_completion_count(self.date)
    
    @property
    def total_correct_entities(self):
        """Get the total number of correct entities across all cells."""
        return sum(self.cell_correct_entities.values())
    
    @property
    def total_guesses(self):
        """Get the total number of guesses made for this grid."""
        from .models import GameResult
        return GameResult.get_total_guesses(self.date)
    
    @property
    def average_score(self):
        """Get the average score for this grid."""
        from .models import GameCompletion
        return GameCompletion.get_average_score(self.date)
    
    @property
    def average_correct_cells(self):
        """Get the average number of correct cells for this grid."""
        from .models import GameCompletion
        return GameCompletion.get_average_correct_cells(self.date)
    
    def get_top_scores(self, limit=10):
        """Get the top scores for this grid."""
        from .models import GameCompletion
        return GameCompletion.get_top_scores(self.date, limit)
    
    def __str__(self):
        return f"Game Grid for {self.date}"
