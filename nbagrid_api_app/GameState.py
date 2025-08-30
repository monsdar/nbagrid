from typing import Any, Dict, Optional, TypedDict

from nbagrid_api_app.tracing import trace_operation


class CellData(TypedDict, total=False):
    player_id: int
    player_name: str
    is_correct: bool
    tier: Optional[str]
    score: Optional[float]


class GameState:
    def __init__(
        self,
        attempts_remaining: int = 10,
        selected_cells: Optional[Dict[str, list[CellData]]] = None,
        is_finished: bool = False,
        total_score: float = 0.0,
    ) -> None:
        self.attempts_remaining: int = attempts_remaining
        self.selected_cells: Dict[str, list[CellData]] = selected_cells or {}
        self.is_finished: bool = is_finished
        self.total_score: float = total_score

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """Create a GameState instance from a dictionary."""
        game_state = cls()
        game_state.attempts_remaining = data.get("attempts_remaining", 10)
        game_state.is_finished = data.get("is_finished", False)
        game_state.total_score = data.get("total_score", 0.0)

        # Handle selected_cells - now contains lists of CellData objects
        selected_cells = data.get("selected_cells", {})
        game_state.selected_cells = {}
        for cell_key, cell_data_list in selected_cells.items():
            # Handle both list and single object formats for backward compatibility
            if not isinstance(cell_data_list, list):
                cell_data_list = [cell_data_list]

            game_state.selected_cells[cell_key] = [
                CellData(
                    player_id=cell_data.get("player_id", 0),
                    player_name=cell_data.get("player_name", ""),
                    is_correct=cell_data.get("is_correct", False),
                    score=cell_data.get("score", 0.0),
                    tier=cell_data.get("tier", "common"),
                )
                for cell_data in cell_data_list
            ]

        return game_state

    def to_dict(self) -> Dict[str, Any]:
        """Convert the GameState instance to a dictionary."""
        return {
            "attempts_remaining": self.attempts_remaining,
            "selected_cells": self.selected_cells,
            "is_finished": self.is_finished,
            "total_score": self.total_score,
        }

    def get_cell_data(self, cell_key: str) -> list[CellData]:
        """Get the data for a specific cell, with proper defaults."""
        return self.selected_cells.get(cell_key, [])

    def add_wrong_guess(self, cell_key: str, player_id: int, player_name: str) -> None:
        """Add a wrong guess to a cell's history."""
        # Create new wrong guess
        new_guess = CellData(player_id=player_id, player_name=player_name, is_correct=False, tier=None, score=0.0)

        # Add to the list
        if cell_key not in self.selected_cells:
            self.selected_cells[cell_key] = []
        self.selected_cells[cell_key].append(new_guess)

    def add_correct_guess(self, cell_key: str, player_id: int, player_name: str, tier: str, score: float) -> None:
        """Set a correct guess for a cell."""
        # Create new correct guess
        new_guess = CellData(player_id=player_id, player_name=player_name, is_correct=True, tier=tier, score=score)

        # Add to the list
        if cell_key not in self.selected_cells:
            self.selected_cells[cell_key] = []
        self.selected_cells[cell_key].append(new_guess)

    def decrement_attempts(self) -> None:
        """Decrement the remaining attempts."""
        self.attempts_remaining = max(0, self.attempts_remaining - 1)

    def check_completion(self, grid_size: int) -> bool:
        """Check if the game is completed."""
        if self.attempts_remaining == 0:
            self.is_finished = True
            return True

        # Check if all cells are correct - now handling lists of CellData
        correct_cells = sum(
            1
            for cell_data_list in self.selected_cells.values()
            if any(cell_data.get("is_correct", False) for cell_data in cell_data_list)
        )
        if correct_cells == grid_size:
            self.is_finished = True
            return True

        return False

    @trace_operation("GameState.get_total_score")
    def get_total_score(self) -> float:
        """Calculate the total score from all correct cells."""
        total = 0.0
        for cell_data_list in self.selected_cells.values():
            for cell_data in cell_data_list:
                if cell_data.get("is_correct", False):
                    total += cell_data.get("score", 0.0)
        self.total_score = total
        return self.total_score
