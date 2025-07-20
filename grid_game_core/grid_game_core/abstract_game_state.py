from abc import abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class CellData:
    """
    Data structure for a cell in the game grid.
    """
    
    entity_id: int
    entity_name: str
    is_correct: bool
    guess_time: Optional[str] = None
    score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CellData':
        """Create from dictionary."""
        return cls(**data)


class BaseGameState:
    """
    Abstract base class for game state management.
    
    This provides the common logic for managing game state across different domains.
    """
    
    def __init__(self):
        """Initialize the game state."""
        self.selected_cells: Dict[str, List[CellData]] = {}
        self.attempts_remaining: int = 9
        self.total_score: float = 0.0
        self.is_finished: bool = False
        self.correct_cells_count: int = 0
    
    @abstractmethod
    def get_entity_manager(self):
        """
        Get the Django manager for the entity model.
        
        Returns:
            Django manager for entities
        """
        pass
    
    @abstractmethod
    def get_game_result_model(self):
        """
        Get the GameResult model class.
        
        Returns:
            GameResult model class
        """
        pass
    
    def add_guess(self, cell_key: str, entity_id: int, entity_name: str, is_correct: bool, score: float = 0.0):
        """
        Add a guess to the game state.
        
        Args:
            cell_key: The cell key (e.g., "0_1")
            entity_id: The entity ID that was guessed
            entity_name: The entity name that was guessed
            is_correct: Whether the guess was correct
            score: The score for this guess
        """
        import datetime
        
        cell_data = CellData(
            entity_id=entity_id,
            entity_name=entity_name,
            is_correct=is_correct,
            guess_time=datetime.datetime.now().isoformat(),
            score=score
        )
        
        if cell_key not in self.selected_cells:
            self.selected_cells[cell_key] = []
        
        self.selected_cells[cell_key].append(cell_data)
        
        if is_correct:
            self.correct_cells_count += 1
            self.total_score += score
        
        self.attempts_remaining -= 1
        
        # Check if game is finished
        if self.correct_cells_count >= 9 or self.attempts_remaining <= 0:
            self.is_finished = True
    
    def get_cell_guesses(self, cell_key: str) -> List[CellData]:
        """
        Get all guesses for a specific cell.
        
        Args:
            cell_key: The cell key
            
        Returns:
            List of cell data for the cell
        """
        return self.selected_cells.get(cell_key, [])
    
    def has_correct_guess(self, cell_key: str) -> bool:
        """
        Check if a cell has a correct guess.
        
        Args:
            cell_key: The cell key
            
        Returns:
            True if the cell has a correct guess
        """
        cell_guesses = self.get_cell_guesses(cell_key)
        return any(guess.is_correct for guess in cell_guesses)
    
    def get_correct_entities(self) -> List[Dict[str, Any]]:
        """
        Get all correctly guessed entities.
        
        Returns:
            List of dictionaries with entity information
        """
        correct_entities = []
        
        for cell_key, guesses in self.selected_cells.items():
            for guess in guesses:
                if guess.is_correct:
                    correct_entities.append({
                        'cell_key': cell_key,
                        'entity_id': guess.entity_id,
                        'entity_name': guess.entity_name,
                        'score': guess.score
                    })
        
        return correct_entities
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert game state to dictionary for serialization.
        
        Returns:
            Dictionary representation of the game state
        """
        return {
            'selected_cells': {
                cell_key: [guess.to_dict() for guess in guesses]
                for cell_key, guesses in self.selected_cells.items()
            },
            'attempts_remaining': self.attempts_remaining,
            'total_score': self.total_score,
            'is_finished': self.is_finished,
            'correct_cells_count': self.correct_cells_count
        }
    
    def from_dict(self, data: Dict[str, Any]) -> 'BaseGameState':
        """
        Load game state from dictionary.
        
        Args:
            data: Dictionary representation of the game state
            
        Returns:
            Self for chaining
        """
        self.selected_cells = {}
        for cell_key, guesses_data in data.get('selected_cells', {}).items():
            self.selected_cells[cell_key] = [
                CellData.from_dict(guess_data) for guess_data in guesses_data
            ]
        
        self.attempts_remaining = data.get('attempts_remaining', 9)
        self.total_score = data.get('total_score', 0.0)
        self.is_finished = data.get('is_finished', False)
        self.correct_cells_count = data.get('correct_cells_count', 0)
        
        return self
    
    def to_json(self) -> str:
        """
        Convert game state to JSON string.
        
        Returns:
            JSON string representation of the game state
        """
        return json.dumps(self.to_dict())
    
    def from_json(self, json_str: str) -> 'BaseGameState':
        """
        Load game state from JSON string.
        
        Args:
            json_str: JSON string representation of the game state
            
        Returns:
            Self for chaining
        """
        data = json.loads(json_str)
        return self.from_dict(data)
    
    def save_game_result(self, date, cell_key: str, entity_id: int):
        """
        Save a game result to the database.
        
        Args:
            date: The game date
            cell_key: The cell key
            entity_id: The entity ID
        """
        GameResult = self.get_game_result_model()
        entity_manager = self.get_entity_manager()
        
        try:
            entity = entity_manager.get(pk=entity_id)
            
            # Check if this result already exists
            existing_result = GameResult.objects.filter(
                date=date,
                cell_key=cell_key,
                content_type__model=entity._meta.model_name,
                object_id=entity_id
            ).first()
            
            if existing_result:
                # Increment guess count
                existing_result.guess_count += 1
                existing_result.save()
            else:
                # Create new result
                GameResult.objects.create(
                    date=date,
                    cell_key=cell_key,
                    content_type=entity._meta.model_name,
                    object_id=entity_id,
                    guess_count=1
                )
                
        except entity_manager.model.DoesNotExist:
            # Entity doesn't exist, skip saving
            pass
    
    def calculate_score(self, entity_id: int, cell_key: str, date) -> float:
        """
        Calculate the score for a correct guess.
        
        Args:
            entity_id: The entity ID
            cell_key: The cell key
            date: The game date
            
        Returns:
            The score for the guess
        """
        GameResult = self.get_game_result_model()
        entity_manager = self.get_entity_manager()
        
        try:
            entity = entity_manager.get(pk=entity_id)
            
            # Get the rarity score for this entity in this cell
            rarity_score = GameResult.get_entity_rarity_score(date, cell_key, entity)
            
            # Calculate score based on rarity (higher rarity = higher score)
            base_score = 100.0
            rarity_bonus = max(0, 50 - rarity_score * 5)  # Less common = higher bonus
            
            return base_score + rarity_bonus
            
        except entity_manager.model.DoesNotExist:
            return 0.0 