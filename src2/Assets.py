# Assets.py
"""
Asset management system for Chessno.

Handles:
- Board and piece sprite loading with case-insensitive filesystem fallback
- High quality aspect-ratio preserving piece scaling
- Dynamic asset pack switching (themes)
- Audio system with custom WAV file support and synthetic procedural fallback
- Configurable geometry and piece sizes
"""

import math
import array
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pygame

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

# Board dimensions used for rendering.
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

# Piece codes mapping to image filenames inside the pack's "pieces" directory.
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

# Optional sounds. Consistent filenames across asset packs.
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

BOARD_IMAGE: Optional[pygame.Surface] = None
PIECE_IMAGES: Dict[str, pygame.Surface] = {}
SOUNDS: Dict[str, Optional[pygame.mixer.Sound]] = {name: None for name in SOUND_FILES}
SOUND_ENABLED: bool = True
SOUND_VOLUME: float = 0.8


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def resolve_file_case_insensitive(directory: Path, target_filename: str) -> Optional[Path]:
    """
    Locate a file in `directory`, matching case-insensitively if an exact match is missing.
    Protects against discrepancies like 'W_BIshop.png' vs 'W_Bishop.png'.
    """
    if not directory.is_dir():
        return None

    # Check direct path first (fast path)
    direct_path = directory / target_filename
    if direct_path.is_file():
        return direct_path

    # Search directory case-insensitively
    target_lower = target_filename.lower()
    for child in directory.iterdir():
        if child.is_file() and child.name.lower() == target_lower:
            return child

    return None


def load_image(path: Path) -> pygame.Surface:
    """Load an image with transparency support and clean error reporting."""
    if not path.is_file():
        raise FileNotFoundError(
            f"\nAsset image not found: {path}\n"
            "Please check that the file exists and is located in the correct asset folder."
        )

    try:
        image = pygame.image.load(str(path))
    except pygame.error as err:
        raise RuntimeError(f"Failed to load image at '{path}': {err}")

    # convert_alpha() requires an active display mode
    if pygame.display.get_surface() is not None:
        image = image.convert_alpha()

    return image


def resize_to_fit(image: pygame.Surface, max_size: Tuple[int, int]) -> pygame.Surface:
    """
    Fit an image inside maximum dimensions without stretching
    or enlarging it beyond its original pixel dimensions.
    """
    max_width, max_height = max_size
    original_width, original_height = image.get_size()

    scale = min(
        max_width / original_width,
        max_height / original_height,
        1.0,
    )

    new_width = max(1, round(original_width * scale))
    new_height = max(1, round(original_height * scale))

    if (new_width, new_height) == image.get_size():
        return image

    return pygame.transform.smoothscale(image, (new_width, new_height))


# ============================================================
# 4. SOUND LOADING & SYNTHESIS
# ============================================================

def _generate_procedural_sound(sound_type: str) -> Optional[pygame.mixer.Sound]:
    """
    Generate pleasant, lightweight procedural audio tones when sound files are absent.
    Ensures tactile audio feedback out-of-the-box.
    """
    try:
        if pygame.mixer.get_init() is None:
            return None

        sample_rate = 22050
        
        # Audio recipes: list of (freq_hz, duration_sec, amplitude)
        recipes = {
            "move": [(420, 0.05, 12000), (320, 0.04, 8000)],
            "capture": [(620, 0.05, 15000), (840, 0.07, 13000)],
            "castle": [(380, 0.04, 11000), (500, 0.06, 12000)],
            "check": [(780, 0.08, 16000), (980, 0.12, 18000)],
            "promotion": [(523, 0.06, 13000), (659, 0.06, 14000), (784, 0.12, 16000)],
            "invalid": [(180, 0.09, 14000), (140, 0.12, 12000)],
            "game_start": [(440, 0.08, 12000), (554, 0.08, 14000), (659, 0.14, 15000)],
            "game_over": [(659, 0.10, 14000), (554, 0.10, 12000), (440, 0.20, 15000)],
        }

        recipe = recipes.get(sound_type)
        if not recipe:
            return None

        total_samples = sum(int(sample_rate * dur) for _, dur, _ in recipe)
        raw_buffer = array.array("h")

        for freq, dur, amp in recipe:
            num_samples = int(sample_rate * dur)
            for i in range(num_samples):
                # Apply envelope decay
                decay = 1.0 - (i / num_samples)
                sample = int(amp * decay * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                raw_buffer.append(max(-32768, min(32767, sample)))

        return pygame.mixer.Sound(buffer=raw_buffer)
    except Exception:
        return None


def load_sounds(pack_dir: Path) -> Dict[str, Optional[pygame.mixer.Sound]]:
    """
    Load available sounds from the selected pack.
    Falls back to procedural tones if audio files are not present in the pack.
    """
    sounds: Dict[str, Optional[pygame.mixer.Sound]] = {name: None for name in SOUND_FILES}

    # Initialize audio mixer if not already active
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    except pygame.error as err:
        print(f"Warning: Audio device unavailable: {err}")
        return sounds

    sounds_dir = pack_dir / "sounds"

    for name, filename in SOUND_FILES.items():
        sound_loaded = False
        if sounds_dir.is_dir():
            file_path = resolve_file_case_insensitive(sounds_dir, filename)
            if file_path:
                try:
                    sound = pygame.mixer.Sound(str(file_path))
                    sound.set_volume(SOUND_VOLUME)
                    sounds[name] = sound
                    sound_loaded = True
                except pygame.error as err:
                    print(f"Warning: Could not load sound '{file_path}': {err}")

        # Fallback to procedural synthesis if file wasn't found
        if not sound_loaded:
            synthetic_sound = _generate_procedural_sound(name)
            if synthetic_sound:
                synthetic_sound.set_volume(SOUND_VOLUME * 0.6)
                sounds[name] = synthetic_sound

    return sounds


# ============================================================
# 5. ASSET PACK LOADING
# ============================================================

def load_assets(pack_name: Optional[str] = None) -> Tuple[pygame.Surface, Dict[str, pygame.Surface]]:
    """
    Load a complete asset pack by folder name.

    Returns:
        (board_surface, dictionary_of_piece_surfaces)
    """
    global ACTIVE_ASSET_PACK, BOARD_IMAGE, PIECE_IMAGES, SOUNDS

    if pack_name is None:
        pack_name = ACTIVE_ASSET_PACK

    pack_dir = ASSET_PACKS_DIR / pack_name

    if not pack_dir.is_dir():
        available = get_available_packs()
        raise FileNotFoundError(
            f"\nAsset pack folder not found: '{pack_name}'\n"
            f"Expected location: {pack_dir}\n"
            f"Available packs: {available}\n"
        )

    # 1. Locate and load board image
    boards_dir = pack_dir / "Boards"
    if not boards_dir.is_dir():
        raise FileNotFoundError(
            f"Asset pack '{pack_name}' is missing the required 'Boards' directory: {boards_dir}"
        )

    board_path = resolve_file_case_insensitive(boards_dir, "DefaultBoard.png")
    if not board_path:
        # Fall back to any image in Boards folder
        board_images = [f for f in boards_dir.iterdir() if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg"]]
        if board_images:
            board_path = board_images[0]
        else:
            raise FileNotFoundError(f"No board image found in: {boards_dir}")

    board = load_image(board_path)
    board = pygame.transform.smoothscale(board, (BOARD_WIDTH, BOARD_HEIGHT))

    # 2. Locate and load piece images
    pieces_dir = pack_dir / "pieces"
    if not pieces_dir.is_dir():
        raise FileNotFoundError(
            f"Asset pack '{pack_name}' is missing the required 'pieces' directory: {pieces_dir}"
        )

    pieces: Dict[str, pygame.Surface] = {}
    missing_pieces = []

    for code, expected_filename in PIECE_FILES.items():
        piece_path = resolve_file_case_insensitive(pieces_dir, expected_filename)
        if not piece_path:
            missing_pieces.append(f"{code} ({expected_filename})")
            continue

        raw_img = load_image(piece_path)
        scaled_img = resize_to_fit(raw_img, PIECE_SIZES[code])
        pieces[code] = scaled_img

    if missing_pieces:
        raise FileNotFoundError(
            f"Asset pack '{pack_name}' is missing required piece images:\n"
            + "\n".join(f"  - {p}" for p in missing_pieces)
        )

    # 3. Load sounds
    sounds = load_sounds(pack_dir)

    # Commit active state
    ACTIVE_ASSET_PACK = pack_name
    BOARD_IMAGE = board
    PIECE_IMAGES = pieces
    SOUNDS = sounds

    print(f"Asset pack loaded: '{ACTIVE_ASSET_PACK}' ({len(pieces)} pieces)")
    return BOARD_IMAGE, PIECE_IMAGES


def switch_asset_pack(pack_name: str) -> Tuple[pygame.Surface, Dict[str, pygame.Surface]]:
    """Switch active theme and return updated board and piece surfaces."""
    return load_assets(pack_name)


def get_active_asset_pack() -> str:
    """Return the name of the currently active theme."""
    return ACTIVE_ASSET_PACK


def get_available_packs() -> List[str]:
    """Return names of valid asset packs present in the assets folder."""
    if not ASSET_PACKS_DIR.is_dir():
        return []

    packs = []
    for folder in ASSET_PACKS_DIR.iterdir():
        if not folder.is_dir():
            continue
        # A valid pack must contain Boards and pieces directories
        if (folder / "Boards").is_dir() and (folder / "pieces").is_dir():
            packs.append(folder.name)

    return sorted(packs)


# ============================================================
# 6. SOUND CONTROLS
# ============================================================

def is_sound_enabled() -> bool:
    return SOUND_ENABLED


def set_sound_enabled(enabled: bool) -> None:
    global SOUND_ENABLED
    SOUND_ENABLED = enabled


def toggle_sound() -> bool:
    global SOUND_ENABLED
    SOUND_ENABLED = not SOUND_ENABLED
    return SOUND_ENABLED


def get_sound(name: str) -> Optional[pygame.mixer.Sound]:
    if name not in SOUND_FILES:
        raise KeyError(f"Unknown sound '{name}'. Available: {list(SOUND_FILES)}")
    return SOUNDS.get(name)


def play_sound(name: str) -> bool:
    """Play sound by identifier (e.g. 'move', 'capture', 'check', 'castle', 'invalid')."""
    if not SOUND_ENABLED:
        return False

    sound = get_sound(name)
    if sound is None:
        return False

    try:
        sound.play()
        return True
    except pygame.error:
        return False


def set_sound_volume(name: str, volume: float) -> bool:
    """Set sound volume between 0.0 and 1.0."""
    if not 0.0 <= volume <= 1.0:
        raise ValueError("Volume must be between 0.0 and 1.0.")

    sound = get_sound(name)
    if sound is None:
        return False

    sound.set_volume(volume)
    return True
