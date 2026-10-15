
import pygame
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SPRITES_DIR = BASE_DIR / "sprites"

BOARD_SIZE = 800
PIECE_SIZE = 65



def load_image(path, max_size=None):
    image = pygame.image.load(str(path)).convert_alpha()

    if max_size is not None:
        original_width, original_height = image.get_size()

        # Support either a number or a (width, height) tuple
        if isinstance(max_size, (tuple, list)):
            max_width, max_height = max_size
        else:
            max_width = max_height = max_size

        # Preserve the original aspect ratio
        scale = min(
            max_width / original_width,
            max_height / original_height
        )

        new_width = max(1, int(original_width * scale))
        new_height = max(1, int(original_height * scale))

        image = pygame.transform.smoothscale(
            image,
            (new_width, new_height)
        )

    return image




def load_assets():
    board_path = SPRITES_DIR / "Boards" / "DefaultBoard.png"

    board = load_image(
        board_path,
        (BOARD_SIZE, BOARD_SIZE)
    )

    # First letter: color
    # Second letter: piece type
    piece_files = {
        "wr": "W_Rook.png",
        "wk": "W_Knight.png",
        "wb": "W_Bishop.png",
        "wa": "W_King.png",
        "wq": "W_Queen.png",
        "wp": "W_Pawn.png",

        "br": "B_Rook.png",
        "bk": "B_Knight.png",
        "bb": "B_Bishop.png",
        "ba": "B_King.png",
        "bq": "B_Queen.png",
        "bp": "B_Pawn.png",
    }

    pieces = {}

    for code, filename in piece_files.items():
        path = SPRITES_DIR / "pieces" / filename
        pieces[code] = load_image(
            path,
            (PIECE_SIZE, PIECE_SIZE)
        )

    return board, pieces
