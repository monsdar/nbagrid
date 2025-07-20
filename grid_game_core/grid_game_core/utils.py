from typing import List, Dict, Any, Optional
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
import logging

logger = logging.getLogger(__name__)


def search_entities(query: str, entity_model, search_fields: List[str], limit: int = 10) -> List[Any]:
    """
    Search for entities using multiple fields.
    
    Args:
        query: Search query string
        entity_model: Django model class for entities
        search_fields: List of field names to search in
        limit: Maximum number of results to return
        
    Returns:
        List of matching entities
    """
    if not query or len(query) < 2:
        return []
    
    # Build Q objects for each search field
    q_objects = Q()
    for field in search_fields:
        q_objects |= Q(**{f"{field}__icontains": query})
    
    try:
        results = entity_model.objects.filter(q_objects).distinct()[:limit]
        return list(results)
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return []


def get_entity_display_name(entity, display_field: str = 'name') -> str:
    """
    Get the display name for an entity.
    
    Args:
        entity: The entity object
        display_field: Field name to use for display
        
    Returns:
        Display name for the entity
    """
    try:
        if hasattr(entity, display_field):
            return getattr(entity, display_field)
        elif hasattr(entity, 'display_name'):
            return entity.display_name
        elif hasattr(entity, 'name'):
            return entity.name
        else:
            return str(entity)
    except Exception as e:
        logger.error(f"Error getting entity display name: {e}")
        return str(entity)


def validate_cell_key(cell_key: str, grid_size: int = 3) -> bool:
    """
    Validate a cell key format.
    
    Args:
        cell_key: Cell key string (e.g., "0_1")
        grid_size: Size of the grid
        
    Returns:
        True if the cell key is valid
    """
    try:
        parts = cell_key.split('_')
        if len(parts) != 2:
            return False
        
        row, col = int(parts[0]), int(parts[1])
        return 0 <= row < grid_size and 0 <= col < grid_size
    except (ValueError, IndexError):
        return False


def parse_cell_key(cell_key: str) -> Optional[tuple[int, int]]:
    """
    Parse a cell key into row and column indices.
    
    Args:
        cell_key: Cell key string (e.g., "0_1")
        
    Returns:
        Tuple of (row, col) or None if invalid
    """
    try:
        parts = cell_key.split('_')
        if len(parts) != 2:
            return None
        
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def build_grid_data(static_filters: List[Any], dynamic_filters: List[Any]) -> List[List[Dict[str, Any]]]:
    """
    Build grid data structure from filters.
    
    Args:
        static_filters: List of static filters (columns)
        dynamic_filters: List of dynamic filters (rows)
        
    Returns:
        Grid data structure
    """
    grid = []
    for row_idx, dynamic_filter in enumerate(dynamic_filters):
        row = []
        for col_idx, static_filter in enumerate(static_filters):
            cell = {
                'filters': [static_filter, dynamic_filter],
                'row': row_idx,
                'col': col_idx,
                'cell_key': f'{row_idx}_{col_idx}'
            }
            row.append(cell)
        grid.append(row)
    return grid


def get_entity_content_type(entity) -> ContentType:
    """
    Get the content type for an entity.
    
    Args:
        entity: The entity object
        
    Returns:
        ContentType for the entity
    """
    return ContentType.objects.get_for_model(entity)


def format_score(score: float) -> str:
    """
    Format a score for display.
    
    Args:
        score: The score to format
        
    Returns:
        Formatted score string
    """
    if score == int(score):
        return str(int(score))
    return f"{score:.1f}"


def calculate_percentage(correct: int, total: int) -> float:
    """
    Calculate percentage with proper handling of edge cases.
    
    Args:
        correct: Number of correct items
        total: Total number of items
        
    Returns:
        Percentage as a float
    """
    if total == 0:
        return 0.0
    return (correct / total) * 100.0


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to an integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to a float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def generate_session_key() -> str:
    """
    Generate a unique session key.
    
    Returns:
        Unique session key string
    """
    import uuid
    return str(uuid.uuid4())


def validate_date_range(start_date, end_date) -> bool:
    """
    Validate that a date range is reasonable.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        True if the date range is valid
    """
    try:
        if start_date >= end_date:
            return False
        
        # Check if the range is not too large (e.g., more than 1 year)
        from datetime import timedelta
        if end_date - start_date > timedelta(days=365):
            return False
        
        return True
    except Exception:
        return False 