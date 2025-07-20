from abc import abstractmethod
from django.db.models import Manager
from typing import Any, Dict, List


class BaseFilter:
    """
    Abstract base class for all game filters.
    
    This provides the common interface that all filters must implement.
    """
    
    @abstractmethod
    def apply_filter(self, entities: Manager) -> Manager:
        """
        Apply the filter to a queryset of entities.
        
        Args:
            entities: Django queryset of entities to filter
            
        Returns:
            Filtered queryset of entities
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Get a human-readable description of the filter.
        
        Returns:
            String description of what the filter does
        """
        pass
    
    @abstractmethod
    def get_entity_stats_str(self, entity: Any) -> str:
        """
        Get a string representation of the entity's stats relevant to this filter. This is displayed to show the user
        the stats of the entity in the cell so he knows why his guess was wrong or what entities would be correct.
        
        Args:
            entity: The entity to get stats for
            
        Returns:
            String representation of the entity's stats
        """
        pass
    
    @abstractmethod 
    def get_detailed_description(self) -> str:
        """
        Get a detailed description of the filter for help/explanation. This is displayed to show the user
        what the filter is about and what he is expected to guess.
        
        Returns:
            Detailed description of the filter
        """
        pass
    
    def __str__(self) -> str:
        return self.get_description()


class BaseDynamicFilter(BaseFilter):
    """
    Abstract base class for dynamic filters that can be tuned.
    
    Dynamic filters have values that can be adjusted to control
    the number of results returned.
    
    TODO: Can we do without the 'static' or 'dynamic' distinction? Filters that can't be tuned should
    simply have a flag `can_be_tuned` set to False.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the dynamic filter with configuration.
        
        Args:
            config: Configuration dictionary for the filter
        """
        self.config = config
        self.current_value = self._get_initial_value()
    
    def _get_initial_value(self) -> Any:
        """
        Get the initial value for the filter.
        
        Returns:
            Initial value for the filter
        """
        import random
        
        if 'initial_value_step' in self.config:
            return random.choice(range(
                self.config['initial_min_value'],
                self.config['initial_max_value'],
                self.config['initial_value_step']
            ))
        
        if 'initial_min_value' in self.config and 'initial_max_value' in self.config:
            return random.randint(
                self.config['initial_min_value'],
                self.config['initial_max_value']
            )
        
        return 0
    
    def widen_filter(self):
        """Widen the filter to include more results."""
        widen_step = -(self.config.get('widen_step', 1))
        
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            widen_step = -widen_step
        
        self.current_value += widen_step
        
        # Ensure the value stays within bounds
        if 'initial_min_value' in self.config and self.current_value < self.config['initial_min_value']:
            self.current_value = self.config['initial_min_value']
        if 'initial_max_value' in self.config and self.current_value > self.config['initial_max_value']:
            self.current_value = self.config['initial_max_value']
    
    def narrow_filter(self):
        """Narrow the filter to include fewer results."""
        narrow_step = self.config.get('narrow_step', 1)
        
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            narrow_step = -narrow_step
        
        self.current_value += narrow_step
        
        # Ensure the value stays within bounds
        if 'initial_min_value' in self.config and self.current_value < self.config['initial_min_value']:
            self.current_value = self.config['initial_min_value']
        if 'initial_max_value' in self.config and self.current_value > self.config['initial_max_value']:
            self.current_value = self.config['initial_max_value']
    
    def get_description(self) -> str:
        """Get the description with current value."""
        description = self.config['description']
        unit = f" {self.config['unit']}" if 'unit' in self.config else ''
        desc_operator = '+'
        
        if 'comparison_type' in self.config and self.config['comparison_type'] == 'lower':
            desc_operator = '-'
        
        display_value = self.current_value
        if isinstance(self.current_value, (int, float)) and self.current_value > 1000000:
            display_value = f"{self.current_value / 1000000:.1f}"
        
        return f"{description} {display_value}{desc_operator}{unit}"
    
    def get_entity_stats_str(self, entity: Any) -> str:
        """Get entity stats string with current value."""
        description = self.config.get('stats_desc', self.config['description'])
        field = self.config['field']
        stat_value = getattr(entity, field)
        
        if isinstance(stat_value, (int, float)) and stat_value > 1000000:
            stat_value = f"{stat_value / 1000000:.1f}"
        
        unit = f" {self.config['unit']}" if 'unit' in self.config else ''
        
        return f"{description} {stat_value}{unit}"
    
    def get_detailed_description(self) -> str:
        """Get detailed description from config or default."""
        return self.config.get('detailed_desc', f'{self.get_description()}')


class BaseStaticFilter(BaseFilter):
    """
    Abstract base class for static filters that don't change.
    
    Static filters have fixed criteria that don't need tuning.
    TODO: This should simply be the BaseFilter class with a flag `can_be_tuned` set to False.
    """
    
    def __init__(self, seed: int = 0):
        """
        Initialize the static filter with a seed for reproducibility.
        
        Args:
            seed: Random seed for deterministic behavior
        """
        self.seed = seed
        self._initialize_filter()
    
    @abstractmethod
    def _initialize_filter(self):
        """
        Initialize the filter's internal state.
        
        This method should be implemented by subclasses to set up
        the filter's criteria based on the seed.
        """
        pass
    
    def get_detailed_description(self) -> str:
        """Get detailed description - can be overridden by subclasses."""
        return self.get_description()


class BaseFilterFactory:
    """
    Abstract factory for creating filters.
    
    This provides a common interface for creating filters in different domains.
    
    TODO: Instead of get_dynamic_filters and get_static_filters, we should have a single method that returns a list of all filters.
    This way we can have a single method that returns a list of all filters, and then we can use the flag `can_be_tuned` to determine
    if the filter is dynamic or static. Whether a filter is tunable is of interest for the GameBuilder which needs to know about this in order to
    build games that are tuned to be within the range of guessable entities.
    """
    
    @abstractmethod
    def get_dynamic_filters(self, seed: int = 0) -> List[BaseDynamicFilter]:
        """
        Get a list of available dynamic filters.
        
        Args:
            seed: Random seed for deterministic behavior
            
        Returns:
            List of dynamic filter instances
        """
        pass
    
    @abstractmethod
    def get_static_filters(self, seed: int = 0) -> List[BaseStaticFilter]:
        """
        Get a list of available static filters.
        
        Args:
            seed: Random seed for deterministic behavior
            
        Returns:
            List of static filter instances
        """
        pass
    
    @abstractmethod
    def create_filter_from_config(self, filter_class: str, config: Dict[str, Any]) -> BaseFilter:
        """
        Create a filter instance from configuration.
        
        Args:
            filter_class: Name of the filter class
            config: Configuration dictionary
            
        Returns:
            Filter instance
        """
        pass
    
    @abstractmethod
    def filter_to_json(self, filter_instance: BaseFilter) -> Dict[str, Any]:
        """
        Convert a filter instance to JSON-serializable format.
        
        Args:
            filter_instance: The filter to serialize
            
        Returns:
            Dictionary representation of the filter
        """
        pass
    
    @abstractmethod
    def filter_from_json(self, filter_data: Dict[str, Any]) -> BaseFilter:
        """
        Create a filter instance from JSON data.
        
        Args:
            filter_data: Dictionary representation of the filter
            
        Returns:
            Filter instance
        """
        pass 