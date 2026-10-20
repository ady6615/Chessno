# coordinates.py
"""
Reusable coordinate conversion utilities for Chessno.

Maps between:
- Screen pixel coordinates (Pygame window space)
- Board matrix coordinates (row: 0-7, col: 0-7)
- Standard chess algebraic squares (chess.Square, 0-63, e.g. A1=0, H8=63)
- Custom piece codes ('wa', 'wq', 'wr', 'wb', 'wk', 'wp', 'ba', 'bq', etc.)
"""

from typing import Optional, Tuple
import pygame
import chess

# Default geometry constants
BOARD_X = 50
BOARD_Y = 50
SQUARE_SIZE = 100
BOARD_SIZE = SQUARE_SIZE * 8

# Mapping between python-chess piece types and project piece code suffixes
# Note: 'a' is used for King (wa / ba) and 'k' for Knight (wk / bk) to preserve existing project assets.
PIECE_TYPE_TO_CODE = {
    chess.PAWN: "p",
    chess.KNIGHT: "k",
    chess.BISHOP: "b",
    chess.ROOK: "r",
    chess.QUEEN: "q",
    chess.KING: "a",
}

CODE_TO_PIECE_TYPE = {code: ptype for ptype, code in PIECE_TYPE_TO_CODE.items()}


def is_inside_board_grid(row: int, col: int) -> bool:
    """Return True if row and col are within the 8x8 chessboard matrix."""
    return 0 <= row < 8 and 0 <= col < 8


def pixel_to_board_coords(
    mouse_pos: Tuple[int, int],
    board_x: int = BOARD_X,
    board_y: int = BOARD_Y,
    square_size: int = SQUARE_SIZE,
) -> Optional[Tuple[int, int]]:
    """
    Convert a pixel position (x, y) to matrix indices (row, col).
    Returns (row, col) if inside the board, or None otherwise.
    """
    mouse_x, mouse_y = mouse_pos
    col = (mouse_x - board_x) // square_size
    row = (mouse_y - board_y) // square_size
    if is_inside_board_grid(row, col):
        return int(row), int(col)
    return None


def board_coords_to_square(row: int, col: int, flipped: bool = False) -> chess.Square:
    """
    Convert (row, col) matrix coordinates to a python-chess square.
    
    Standard view (flipped=False, White at bottom):
      - row 0 is Rank 8 (top of screen)
      - row 7 is Rank 1 (bottom of screen)
      - col 0 is File a (left)
      - col 7 is File h (right)
    
    Flipped view (flipped=True, Black at bottom):
      - row 0 is Rank 1 (top of screen)
      - row 7 is Rank 8 (bottom of screen)
      - col 0 is File h (left)
      - col 7 is File a (right)
    """
    if not is_inside_board_grid(row, col):
        raise ValueError(f"Matrix coordinates out of bounds: row={row}, col={col}")

    if not flipped:
        file_idx = col
        rank_idx = 7 - row
    else:
        file_idx = 7 - col
        rank_idx = row

    return chess.square(file_idx, rank_idx)


def square_to_board_coords(square: chess.Square, flipped: bool = False) -> Tuple[int, int]:
    """
    Convert a python-chess square to (row, col) matrix coordinates.
    """
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)

    if not flipped:
        col = file_idx
        row = 7 - rank_idx
    else:
        col = 7 - file_idx
        row = rank_idx

    return int(row), int(col)


def pixel_to_square(
    mouse_pos: Tuple[int, int],
    flipped: bool = False,
    board_x: int = BOARD_X,
    board_y: int = BOARD_Y,
    square_size: int = SQUARE_SIZE,
) -> Optional[chess.Square]:
    """Directly convert pixel position to chess.Square, or None if outside the board."""
    coords = pixel_to_board_coords(mouse_pos, board_x, board_y, square_size)
    if coords is None:
        return None
    return board_coords_to_square(coords[0], coords[1], flipped=flipped)


def square_to_rect(
    square: chess.Square,
    flipped: bool = False,
    board_x: int = BOARD_X,
    board_y: int = BOARD_Y,
    square_size: int = SQUARE_SIZE,
) -> pygame.Rect:
    """Return the Pygame Rect representing a chess square on screen."""
    row, col = square_to_board_coords(square, flipped=flipped)
    return pygame.Rect(
        board_x + col * square_size,
        board_y + row * square_size,
        square_size,
        square_size,
    )


def square_to_piece_center(
    square: chess.Square,
    image_width: int,
    image_height: int,
    flipped: bool = False,
    board_x: int = BOARD_X,
    board_y: int = BOARD_Y,
    square_size: int = SQUARE_SIZE,
) -> Tuple[int, int]:
    """Calculate the top-left (x, y) to draw a piece centered on its square."""
    rect = square_to_rect(square, flipped=flipped, board_x=board_x, board_y=board_y, square_size=square_size)
    x = rect.x + (square_size - image_width) // 2
    y = rect.y + (square_size - image_height) // 2
    return x, y


def piece_to_code(piece: Optional[chess.Piece]) -> Optional[str]:
    """Convert a chess.Piece instance into the project piece code (e.g. 'wa', 'bq')."""
    if piece is None:
        return None
    color = "w" if piece.color == chess.WHITE else "b"
    kind = PIECE_TYPE_TO_CODE.get(piece.piece_type)
    if kind is None:
        return None
    return f"{color}{kind}"


def code_to_piece(code: Optional[str]) -> Optional[chess.Piece]:
    """Convert a project piece code (e.g. 'wa', 'bq') into a chess.Piece instance."""
    if not code or len(code) != 2:
        return None
    color = chess.WHITE if code[0] == "w" else chess.BLACK
    piece_type = CODE_TO_PIECE_TYPE.get(code[1])
    if piece_type is None:
        return None
    return chess.Piece(piece_type, color)
