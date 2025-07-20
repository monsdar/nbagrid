from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import os


@dataclass
class DomainConfig:
    """
    Configuration for a specific domain (NBA, Countries, etc.).
    """
    
    # Basic domain information
    domain_name: str
    domain_display_name: str
    domain_description: str
    
    # Entity configuration
    entity_model: str
    entity_display_field: str = 'name'
    search_fields: List[str] = field(default_factory=lambda: ['name'])
    
    # Filter configuration
    filter_classes: List[str] = field(default_factory=list)
    dynamic_filter_configs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Game configuration
    grid_size: int = 3
    min_results: int = 5
    max_results: int = 40
    max_attempts: int = 9
    
    # Theme configuration
    theme: Dict[str, str] = field(default_factory=dict)
    
    # URLs and routing
    base_url: str = ''
    api_prefix: str = 'api'
    
    # Database configuration
    database_prefix: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'domain_name': self.domain_name,
            'domain_display_name': self.domain_display_name,
            'domain_description': self.domain_description,
            'entity_model': self.entity_model,
            'entity_display_field': self.entity_display_field,
            'search_fields': self.search_fields,
            'filter_classes': self.filter_classes,
            'dynamic_filter_configs': self.dynamic_filter_configs,
            'grid_size': self.grid_size,
            'min_results': self.min_results,
            'max_results': self.max_results,
            'max_attempts': self.max_attempts,
            'theme': self.theme,
            'base_url': self.base_url,
            'api_prefix': self.api_prefix,
            'database_prefix': self.database_prefix,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainConfig':
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_json_file(cls, file_path: str) -> 'DomainConfig':
        """Load configuration from JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def save_to_json_file(self, file_path: str):
        """Save configuration to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class ConfigManager:
    """
    Manager for domain configurations.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or os.path.join(os.getcwd(), 'configs')
        self.configs: Dict[str, DomainConfig] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all configuration files from the config directory."""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            return
        
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                domain_name = filename[:-5]  # Remove .json extension
                file_path = os.path.join(self.config_dir, filename)
                try:
                    config = DomainConfig.from_json_file(file_path)
                    self.configs[domain_name] = config
                except Exception as e:
                    print(f"Error loading config {filename}: {e}")
    
    def get_config(self, domain_name: str) -> Optional[DomainConfig]:
        """
        Get configuration for a specific domain.
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            Domain configuration or None if not found
        """
        return self.configs.get(domain_name)
    
    def add_config(self, config: DomainConfig):
        """
        Add or update a domain configuration.
        
        Args:
            config: Domain configuration to add
        """
        self.configs[config.domain_name] = config
        file_path = os.path.join(self.config_dir, f"{config.domain_name}.json")
        config.save_to_json_file(file_path)
    
    def remove_config(self, domain_name: str):
        """
        Remove a domain configuration.
        
        Args:
            domain_name: Name of the domain to remove
        """
        if domain_name in self.configs:
            del self.configs[domain_name]
            file_path = os.path.join(self.config_dir, f"{domain_name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def list_domains(self) -> List[str]:
        """
        Get list of all domain names.
        
        Returns:
            List of domain names
        """
        return list(self.configs.keys())
    
    def get_all_configs(self) -> Dict[str, DomainConfig]:
        """
        Get all domain configurations.
        
        Returns:
            Dictionary of domain configurations
        """
        return self.configs.copy()


# Example configurations for different domains
NBA_CONFIG = DomainConfig(
    domain_name='nba',
    domain_display_name='NBA Players',
    domain_description='Grid game featuring NBA basketball players',
    entity_model='Player',
    entity_display_field='display_name',
    search_fields=['name', 'display_name'],
    filter_classes=[
        'PositionFilter',
        'TeamFilter',
        'CountryFilter',
        'AllStarFilter',
        'MVPFilter',
        'HeightFilter',
        'WeightFilter',
        'PPGFilter',
        'APGFilter',
        'RPGFilter'
    ],
    dynamic_filter_configs=[
        {
            'name': 'HeightFilter',
            'description': 'Height',
            'field': 'height_cm',
            'unit': 'cm',
            'initial_min_value': 180,
            'initial_max_value': 220,
            'widen_step': 5,
            'narrow_step': 5
        },
        {
            'name': 'WeightFilter',
            'description': 'Weight',
            'field': 'weight_kg',
            'unit': 'kg',
            'initial_min_value': 70,
            'initial_max_value': 140,
            'widen_step': 5,
            'narrow_step': 5
        },
        {
            'name': 'PPGFilter',
            'description': 'Career PPG',
            'field': 'career_ppg',
            'unit': '',
            'initial_min_value': 5,
            'initial_max_value': 30,
            'widen_step': 1,
            'narrow_step': 1
        }
    ],
    theme={
        'primary_color': '#1d428a',
        'secondary_color': '#c8102e',
        'background_color': '#ffffff',
        'text_color': '#333333',
        'logo_url': '/static/nba_logo.png'
    },
    base_url='/nba',
    api_prefix='api',
    database_prefix='nba'
)

COUNTRIES_CONFIG = DomainConfig(
    domain_name='countries',
    domain_display_name='Countries',
    domain_description='Grid game featuring countries of the world',
    entity_model='Country',
    entity_display_field='name',
    search_fields=['name', 'code', 'capital'],
    filter_classes=[
        'ContinentFilter',
        'PopulationFilter',
        'AreaFilter',
        'GDPFilter',
        'RegionFilter',
        'LanguageFilter',
        'CurrencyFilter'
    ],
    dynamic_filter_configs=[
        {
            'name': 'PopulationFilter',
            'description': 'Population',
            'field': 'population',
            'unit': 'million',
            'initial_min_value': 1,
            'initial_max_value': 1500,
            'widen_step': 50,
            'narrow_step': 50
        },
        {
            'name': 'AreaFilter',
            'description': 'Area',
            'field': 'area_km2',
            'unit': 'km²',
            'initial_min_value': 100,
            'initial_max_value': 17000000,
            'widen_step': 1000,
            'narrow_step': 1000
        }
    ],
    theme={
        'primary_color': '#2e8b57',
        'secondary_color': '#4682b4',
        'background_color': '#f5f5f5',
        'text_color': '#333333',
        'logo_url': '/static/globe_logo.png'
    },
    base_url='/countries',
    api_prefix='api',
    database_prefix='countries'
)

# Default configuration manager instance
config_manager = ConfigManager() 