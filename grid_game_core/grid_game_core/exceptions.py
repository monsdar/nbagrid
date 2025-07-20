class GridGameCoreException(Exception):
    """Base exception for grid game core."""
    pass


class EntityNotFoundError(GridGameCoreException):
    """Raised when an entity is not found."""
    pass


class InvalidFilterError(GridGameCoreException):
    """Raised when a filter is invalid."""
    pass


class GameStateError(GridGameCoreException):
    """Raised when there's an error with game state."""
    pass


class ConfigurationError(GridGameCoreException):
    """Raised when there's a configuration error."""
    pass


class InvalidCellKeyError(GridGameCoreException):
    """Raised when a cell key is invalid."""
    pass


class GameCompletionError(GridGameCoreException):
    """Raised when there's an error with game completion."""
    pass


class FilterFactoryError(GridGameCoreException):
    """Raised when there's an error with filter factory."""
    pass


class EntitySearchError(GridGameCoreException):
    """Raised when there's an error searching for entities."""
    pass 