# ChessMatrix.py
"""
Backward-compatibility matrix interface for Chessno.

Connects the legacy ChessMatrix API with the authoritative GameState engine.
Preserves existing functions (inside_board, is_valid_move, move_piece, matrix)
while ensuring complete FIDE chess rule enforcement under the hood.
"""

from typing import Optional, List, Tuple
import chess

from coordinates import (
    is_inside_board_grid,
    board_coords_to_square,
    piece_to_code,
    code_to_piece,
)
from game_engine import GameState

EMPTY = None

# Global game state instance for matrix-level access
_default_game_state = GameState()


def get_active_game_state() -> GameState:
    """Return the underlying authoritative GameState."""
    return _default_game_state


def set_active_game_state(state: GameState) -> None:
    """Update the active GameState used by this matrix module."""
    global _default_game_state
    _default_game_state = state


def inside_board(row: int, col: int) -> bool:
    """Check if (row, col) lies within the 8x8 chessboard."""
    return is_inside_board_grid(row, col)


def get_matrix(flipped: bool = False) -> List[List[Optional[str]]]:
    """Return an 8x8 matrix representing current piece positions."""
    return _default_game_state.to_matrix(flipped=flipped)


class _MatrixProxy:
    """
    Dynamic proxy that behaves like an 8x8 list while always reflecting
    the authoritative GameState board state in real time.
    """
    def __getitem__(self, row: int):
        if not (0 <= row < 8):
            raise IndexError("Row out of range (0-7)")
        current_matrix = get_matrix()
        return current_matrix[row]

    def __setitem__(self, row: int, value):
        # Direct matrix assignment is discouraged, but supported for compatibility
        pass

    def __iter__(self):
        return iter(get_matrix())

    def __len__(self):
        return 8


# matrix property that always mirrors the authoritative board
matrix = _MatrixProxy()


def is_valid_move(start: Tuple[int, int], end: Tuple[int, int], flipped: bool = False) -> bool:
    """
    Check if a move from start=(r1, c1) to end=(r2, c2) is legal under chess rules.
    """
    r1, c1 = start
    r2, c2 = end

    if not inside_board(r1, c1) or not inside_board(r2, c2):
        return False

    if start == end:
        return False

    try:
        from_sq = board_coords_to_square(r1, c1, flipped=flipped)
        to_sq = board_coords_to_square(r2, c2, flipped=flipped)
    except Exception:
        return False

    return _default_game_state.is_legal_move(from_sq, to_sq)


def move_piece(
    start: Tuple[int, int],
    end: Tuple[int, int],
    promotion: Optional[int] = None,
    flipped: bool = False,
) -> bool:
    """
    Execute a move from start=(r1, c1) to end=(r2, c2).
    Returns True if the move was legal and committed, False otherwise.
    """
    r1, c1 = start
    r2, c2 = end

    if not inside_board(r1, c1) or not inside_board(r2, c2):
        return False

    try:
        from_sq = board_coords_to_square(r1, c1, flipped=flipped)
        to_sq = board_coords_to_square(r2, c2, flipped=flipped)
    except Exception:
        return False

    result = _default_game_state.make_move(from_sq, to_sq, promotion=promotion)
    return result.success


def reset_board() -> None:
    """Reset the board to the standard starting position."""
    _default_game_state.reset()
