
import pygame
from pathlib import Path

# Resolve paths relative to this file.
BASE_DIR = Path(__file__).resolve().parent
SPRITES_DIR = BASE_DIR / "sprites"

BOARD_WIDTH = 800
BOARD_HEIGHT = 800

# Customize each piece independently.
# Format: (maximum_width, maximum_height)
PIECE_SIZES = {
    "wr": (80, 80),
    "wk": (80, 80),
    "wb": (80, 80),
    "wa": (90, 90),
    "wq": (90, 90),
    "wp": (90, 90),

    "br": (80, 80),
    "bk": (80, 80),
    "bb": (80, 80),
    "ba": (90, 90),
    "bq": (90, 90),
    "bp": (9, 9),
}

PIECE_FILES = {
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


def load_image(path, max_size=None):
    """Load an image and optionally fit it without stretching."""

    if not path.is_file():
        raise FileNotFoundError(
            f"Image not found: {path}\n"
            f"Check your sprites folder and filename."
        )

    image = pygame.image.load(str(path)).convert_alpha()

    if max_size is not None:
        max_width, max_height = max_size
        original_width, original_height = image.get_size()

        scale = min(
            max_width / original_width,
            max_height / original_height
        )

        # Never enlarge the source image automatically.
        # scale = min(scale, 1.0)

        # new_width = max(1, round(original_width * scale))
        # new_height = max(1, round(original_height * scale))

        # image = pygame.transform.smoothscale(
        #     image,
        #     (new_width, new_height)
        # )

    return image


def load_assets():
    """Load the board and all piece sprites."""

    board_path = SPRITES_DIR / "Boards" / "DefaultBoard.png"

    board = load_image(
        board_path,
        (BOARD_WIDTH, BOARD_HEIGHT)
    )

    pieces = {}

    for code, filename in PIECE_FILES.items():
        piece_path = SPRITES_DIR / "pieces" / filename

        pieces[code] = load_image(
            piece_path,
            PIECE_SIZES[code]
        )

    return board, pieces
