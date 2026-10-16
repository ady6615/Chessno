
# Assets.py

import pygame
from pathlib import Path


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# All asset packs are stored inside this directory.
ASSET_PACKS_DIR = BASE_DIR / "assets"

# Default theme loaded when the game starts.
DEFAULT_ASSET_PACK = "Default"

# Current active theme.
ACTIVE_ASSET_PACK = DEFAULT_ASSET_PACK

# Board dimensions used by main.py.
BOARD_WIDTH = 800
BOARD_HEIGHT = 800

# ------------------------------------------------------------
# Individual piece sizes.
# Format: piece_code: (maximum_width, maximum_height)
#
# These are maximum bounds, not forced image dimensions.
# Original aspect ratios are preserved.
# ------------------------------------------------------------

PIECE_SIZES = {
    "wr": (80, 80),
    "wk": (80, 80),
    "wb": (80, 80),
    "wa": (90, 90),
    "wq": (90, 90),
    "wp": (65, 65),

    "br": (80, 80),
    "bk": (80, 80),
    "bb": (80, 80),
    "ba": (90, 90),
    "bq": (90, 90),
    "bp": (65, 65),
}

# Piece codes must match those used in ChessMatrix.py.
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

# Optional sounds. The filenames should be consistent
# between every asset pack.
SOUND_FILES = {
    "move": "Move.wav",
    "capture": "Capture.wav",
    "invalid": "Invalid.wav",
    "check": "Check.wav",
    "castle": "Castle.wav",
    "promotion": "Promotion.wav",
    "game_start": "GameStart.wav",
    "game_over": "GameOver.wav",
}


# ============================================================
# 2. ASSET STATE
# ============================================================

BOARD_IMAGE = None
PIECE_IMAGES = {}
SOUNDS = {name: None for name in SOUND_FILES}


# ============================================================
# 3. IMAGE LOADING
# ============================================================

def load_image(path):
    """Load an image with transparency support."""

    if not path.is_file():
        raise FileNotFoundError(
            f"\nAsset image not found:\n{path}\n\n"
            "Check the asset pack folder and filename."
        )

    image = pygame.image.load(str(path))

    # convert_alpha() requires a display mode to exist.
    if pygame.display.get_surface() is not None:
        image = image.convert_alpha()

    return image


def resize_to_fit(image, max_size):
    """
    Fit an image inside maximum dimensions without stretching
    or enlarging it beyond its original pixel dimensions.
    """

    max_width, max_height = max_size

    original_width, original_height = image.get_size()

    scale = min(
        max_width / original_width,
        max_height / original_height,
        1.0
    )

    new_width = max(1, round(original_width * scale))
    new_height = max(1, round(original_height * scale))

    if (new_width, new_height) == image.get_size():
        return image

    return pygame.transform.smoothscale(
        image,
        (new_width, new_height)
    )


# ============================================================
# 4. SOUND LOADING
# ============================================================

def load_sounds(pack_dir):
    """
    Load available sounds from the selected pack.

    Missing sound files are allowed. Their values remain None.
    """

    sounds = {name: None for name in SOUND_FILES}

    sounds_dir = pack_dir / "sounds"

    if not sounds_dir.is_dir():
        return sounds

    # Identify available sound files before initializing audio.
    available = {}

    for name, filename in SOUND_FILES.items():
        path = sounds_dir / filename

        if path.is_file():
            available[name] = path

    if not available:
        return sounds

    # Initialize the audio mixer if necessary.
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
    except pygame.error as error:
        print(f"Warning: Audio is unavailable: {error}")
        return sounds

    # Load each available sound independently.
    for name, path in available.items():
        try:
            sounds[name] = pygame.mixer.Sound(str(path))
        except pygame.error as error:
            print(f"Warning: Could not load sound '{path}': {error}")

    return sounds


# ============================================================
# 5. LOAD AN ASSET PACK
# ============================================================

def load_assets(pack_name=None):
    """
    Load a complete asset pack.

    Usage:
        board, pieces = load_assets()
        board, pieces = load_assets("Modern")

    Returns:
        board image
        dictionary containing piece images
    """

    global ACTIVE_ASSET_PACK
    global BOARD_IMAGE, PIECE_IMAGES, SOUNDS

    # If no pack is specified, use the active pack.
    if pack_name is None:
        pack_name = ACTIVE_ASSET_PACK

    pack_dir = ASSET_PACKS_DIR / pack_name

    if not pack_dir.is_dir():
        available = get_available_packs()

        raise FileNotFoundError(
            f"\nAsset pack not found: '{pack_name}'\n"
            f"Expected folder: {pack_dir}\n"
            f"Available packs: {available}\n"
        )

    # Load the required board image.
    board_path = pack_dir / "Boards" / "DefaultBoard.png"
    board = load_image(board_path)

    # The board is expected to fill the board area.
    board = pygame.transform.smoothscale(
        board,
        (BOARD_WIDTH, BOARD_HEIGHT)
    )

    # Load all required piece images.
    pieces = {}

    for code, filename in PIECE_FILES.items():
        piece_path = pack_dir / "pieces" / filename

        image = load_image(piece_path)
        image = resize_to_fit(image, PIECE_SIZES[code])

        pieces[code] = image

    # Load optional sounds.
    sounds = load_sounds(pack_dir)

    # Update the active state only after required images load.
    ACTIVE_ASSET_PACK = pack_name
    BOARD_IMAGE = board
    PIECE_IMAGES = pieces
    SOUNDS = sounds

    print(f"Asset pack loaded: {ACTIVE_ASSET_PACK}")

    return BOARD_IMAGE, PIECE_IMAGES


# ============================================================
# 6. SWITCH ASSET PACKS
# ============================================================

def switch_asset_pack(pack_name):
    """
    Switch to a different theme.

    Usage in main.py:
        board_image, piece_images = Assets.switch_asset_pack("Modern")
    """

    return load_assets(pack_name)


def get_active_asset_pack():
    """Return the name of the active theme."""

    return ACTIVE_ASSET_PACK


def get_available_packs():
    """Return the names of folders that look like asset packs."""

    if not ASSET_PACKS_DIR.is_dir():
        return []

    packs = []

    for folder in ASSET_PACKS_DIR.iterdir():
        if not folder.is_dir():
            continue

        # A valid pack must contain both required directories.
        if (
            (folder / "Boards").is_dir()
            and (folder / "pieces").is_dir()
        ):
            packs.append(folder.name)

    return sorted(packs)


# ============================================================
# 7. SOUND ACCESS
# ============================================================

def get_sound(name):
    """Return a Sound object, or None if unavailable."""

    if name not in SOUND_FILES:
        raise KeyError(
            f"Unknown sound '{name}'. "
            f"Available sounds: {list(SOUND_FILES)}"
        )

    return SOUNDS.get(name)


def play_sound(name):
    """
    Play a loaded sound.

    Returns True if playback was requested successfully,
    False if the sound is missing or audio is unavailable.
    """

    sound = get_sound(name)

    if sound is None:
        return False

    try:
        sound.play()
        return True
    except pygame.error:
        return False


def set_sound_volume(name, volume):
    """Set a sound's volume from 0.0 to 1.0."""

    if not 0.0 <= volume <= 1.0:
        raise ValueError("Volume must be between 0.0 and 1.0.")

    sound = get_sound(name)

    if sound is None:
        return False

    sound.set_volume(volume)
    return True
