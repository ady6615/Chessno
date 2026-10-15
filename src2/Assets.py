
import pygame
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SPRITES_DIR = BASE_DIR / "sprites"

BOARD_SIZE = 800
PIECE_SIZE = 80

def load_image(path, size=None):
    image = pygame.image.load(str(path)).convert_alpha()

    if size is not None:
        image = pygame.transform.smoothscale(image, size)

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
