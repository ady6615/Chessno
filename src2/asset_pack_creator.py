# asset_pack_creator.py
"""
Asset Pack Creator for Chessno.

Allows users to:
1. Name their custom asset pack.
2. Choose custom piece pictures from their local device one-by-one.
3. Automatically resize chosen images to fit standard chessboard squares
   while preserving original aspect ratios and transparency.
4. Store the pack in the local assets directory structure so it can be
   immediately accessed and switched to by the game's asset system.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import os
import re
import shutil
import pygame
import chess

from coordinates import piece_to_code
import Assets

# Target dimensions for resized piece images saved to disk (crisp high-DPI bounds)
MAX_PIECE_SAVE_SIZE = (180, 180)

# Full specification of the 12 standard chess pieces in an asset pack
PIECE_SPECS: List[Dict[str, Any]] = [
    # White pieces
    {"code": "wa", "name": "White King", "file": "W_King.png", "team": "White", "size": (90, 90)},
    {"code": "wq", "name": "White Queen", "file": "W_Queen.png", "team": "White", "size": (90, 90)},
    {"code": "wr", "name": "White Rook", "file": "W_Rook.png", "team": "White", "size": (80, 80)},
    {"code": "wb", "name": "White Bishop", "file": "W_Bishop.png", "team": "White", "size": (80, 80)},
    {"code": "wk", "name": "White Knight", "file": "W_Knight.png", "team": "White", "size": (80, 80)},
    {"code": "wp", "name": "White Pawn", "file": "W_Pawn.png", "team": "White", "size": (65, 65)},
    # Black pieces
    {"code": "ba", "name": "Black King", "file": "B_King.png", "team": "Black", "size": (90, 90)},
    {"code": "bq", "name": "Black Queen", "file": "B_Queen.png", "team": "Black", "size": (90, 90)},
    {"code": "br", "name": "Black Rook", "file": "B_Rook.png", "team": "Black", "size": (80, 80)},
    {"code": "bb", "name": "Black Bishop", "file": "B_Bishop.png", "team": "Black", "size": (80, 80)},
    {"code": "bk", "name": "Black Knight", "file": "B_Knight.png", "team": "Black", "size": (80, 80)},
    {"code": "bp", "name": "Black Pawn", "file": "B_Pawn.png", "team": "Black", "size": (65, 65)},
]

WHITE_SPECS = [s for s in PIECE_SPECS if s["team"] == "White"]
BLACK_SPECS = [s for s in PIECE_SPECS if s["team"] == "Black"]
SPEC_BY_CODE = {s["code"]: s for s in PIECE_SPECS}


def sanitize_pack_name(name: str) -> str:
    """Sanitize user input to create a safe, valid directory name."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean[:30]


def open_file_dialog_for_image(title: str = "Select Piece Image") -> Optional[str]:
    """
    Open native OS file picker to let the user select a picture from their device.
    Supports PNG, JPG, JPEG, BMP, and WEBP.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        file_path = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
                ("PNG images", "*.png"),
                ("JPEG images", "*.jpg;*.jpeg"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return file_path if file_path else None
    except Exception as err:
        print(f"Warning: Could not open file dialog: {err}")
        return None


def open_folder_dialog(title: str = "Select Folder Containing Piece Images") -> Optional[str]:
    """Open native OS directory picker for convenient batch piece importing."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder_path = filedialog.askdirectory(title=title)
        root.destroy()
        return folder_path if folder_path else None
    except Exception as err:
        print(f"Warning: Could not open folder dialog: {err}")
        return None


def resize_image_for_board(surface: pygame.Surface, target_max: Tuple[int, int] = (160, 160)) -> pygame.Surface:
    """
    Resize a raw piece surface to fit within the board square preserving aspect ratio.
    Ensures crisp rendering with smoothscale and alpha preservation.
    """
    orig_w, orig_h = surface.get_size()
    if orig_w <= 0 or orig_h <= 0:
        return surface

    max_w, max_h = target_max
    scale = min(max_w / orig_w, max_h / orig_h)
    new_w = max(1, round(orig_w * scale))
    new_h = max(1, round(orig_h * scale))

    if (new_w, new_h) == (orig_w, orig_h):
        return surface

    return pygame.transform.smoothscale(surface, (new_w, new_h))


def match_piece_file(filepath: Path, siblings: Optional[List[Path]] = None) -> Optional[str]:
    """
    Intelligently identify the chess piece code (e.g. 'wa', 'bq') from a file path.
    Supports:
    - Standard project filenames: W_King.png, W_Knight.png, B_Rook.png, etc.
    - Long names: white_king.png, black_queen.png, white_knight.png, etc.
    - Inverted names: king_white.png, knight_black.png, rook_w.png, pawn_b.png, etc.
    - Standard algebraic codes: wK.png, wN.png, wR.png, wB.png, wQ.png, wP.png, bK.png, etc.
    - Chessno project codes: wa.png, wk.png, wr.png, wb.png, wq.png, wp.png, ba.png, etc.
    - Directory-based: white/king.png, black/knight.png, w/r.png, b/p.png, etc.
    - Wikimedia/cburnett sets: Chess_klt45.png, Chess_ndt45.png, etc.
    - Colloquial piece terms: horse -> knight, castle/tower -> rook.
    """
    p = Path(filepath)
    stem = p.stem.lower()
    parent = p.parent.name.lower()

    # 1. Color detection
    color = None

    # Check parent directory name
    if parent in ("white", "whites", "w", "light", "white_pieces", "white-pieces"):
        color = "w"
    elif parent in ("black", "blacks", "b", "dark", "black_pieces", "black-pieces"):
        color = "b"

    # Check Wikimedia format (e.g. Chess_klt45, Chess_kdt45)
    if not color:
        if "lt" in stem or "_l" in stem or "-l" in stem:
            color = "w"
        elif "dt" in stem or "_d" in stem or "-d" in stem:
            color = "b"

    # Check prefixes
    if not color:
        if stem.startswith(("white_", "white-", "white ", "white.", "w_", "w-", "w.")):
            color = "w"
        elif stem.startswith(("black_", "black-", "black ", "black.", "b_", "b-", "b.")):
            color = "b"

    # Check suffixes
    if not color:
        if stem.endswith(("_white", "-white", " white", ".white", "_w", "-w")):
            color = "w"
        elif stem.endswith(("_black", "-black", " black", ".black", "_b", "-b")):
            color = "b"

    # Check 2-letter codes: e.g. wp, wr, wn, wb, wq, wk, wa
    if not color and len(stem) == 2:
        if stem[0] == "w":
            color = "w"
        elif stem[0] == "b":
            color = "b"

    # Token matching in separated words
    if not color:
        words = re.split(r"[_\-\s.]+", stem)
        if any(w in ("white", "w", "light") for w in words):
            color = "w"
        elif any(w in ("black", "b", "dark") for w in words):
            color = "b"

    if not color:
        return None

    # 2. Piece kind detection
    # CRITICAL: Full piece names MUST be tested BEFORE single-letter abbreviations!
    # Otherwise 'rook' ends with 'k' -> mistakenly matches King!
    # And 'knight' contains '_k' -> mistakenly matches King!
    # And 'pawn' ends with 'n' -> mistakenly matches Knight!

    # A) Knight (check knight before king so 'knight' is never mistaken for 'k'!)
    if any(k in stem for k in ("knight", "night", "horse", "caballo", "cheval", "springer", "cavalo")):
        return f"{color}k"

    # B) King
    if any(k in stem for k in ("king", "könig", "koenig", "roi", "rey")):
        return f"{color}a"

    # C) Queen
    if any(k in stem for k in ("queen", "dame", "dama", "reine")):
        return f"{color}q"

    # D) Rook
    if any(k in stem for k in ("rook", "castle", "tower", "turm", "torre", "tour")):
        return f"{color}r"

    # E) Bishop
    if any(k in stem for k in ("bishop", "alfil", "fou", "läufer", "laeufer", "alfiere")):
        return f"{color}b"

    # F) Pawn
    if any(k in stem for k in ("pawn", "peon", "peón", "pion", "bauer", "pedina")):
        return f"{color}p"

    # 3. Short Notation / Abbreviations
    # Strip color and common prefixes/suffixes
    cleaned = stem
    for pfx in ("white_", "white-", "white ", "white.", "w_", "w-", "w.", "chess_", "chess-"):
        if cleaned.startswith(pfx):
            cleaned = cleaned[len(pfx):]
    for sfx in ("_white", "-white", " white", ".white", "_w", "-w", "lt45", "dt45", "lt", "dt", "45"):
        if cleaned.endswith(sfx):
            cleaned = cleaned[:-len(sfx)]
    cleaned = cleaned.strip("_- .")

    # If stem was 2 chars like 'wr' or 'bn':
    if len(stem) == 2 and stem[0] in ("w", "b"):
        cleaned = stem[1]

    # Standard algebraic notation:
    # K=King ('a'), Q=Queen ('q'), R=Rook ('r'), B=Bishop ('b'), N=Knight ('k'), P=Pawn ('p')
    # Chessno notation:
    # A=King ('a'), K=Knight ('k')
    if cleaned in ("n", "kn", "kt"):
        return f"{color}k"
    elif cleaned in ("a",):
        return f"{color}a"
    elif cleaned in ("k",):
        # Disambiguate 'k':
        # If siblings contain 'wa' or 'ba' (Chessno naming), then 'k' is Knight ('k').
        # Otherwise, in standard algebraic chess notation (K=King, N=Knight), 'k' is King ('a').
        if siblings:
            sib_stems = {s.stem.lower() for s in siblings}
            if f"{color}a" in sib_stems or f"{color}_a" in sib_stems:
                return f"{color}k"
        return f"{color}a"
    elif cleaned in ("q",):
        return f"{color}q"
    elif cleaned in ("r",):
        return f"{color}r"
    elif cleaned in ("b",):
        return f"{color}b"
    elif cleaned in ("p",):
        return f"{color}p"

    return None


def save_asset_pack(
    pack_name: str,
    piece_paths: Dict[str, str],
    custom_board_path: Optional[str] = None,
    default_piece_images: Optional[Dict[str, pygame.Surface]] = None,
) -> Tuple[bool, str]:
    """
    Assemble, resize, and save the complete asset pack to disk.
    
    1. Validates pack name and directory safety.
    2. Creates <pack_name>/Boards and <pack_name>/pieces directories.
    3. Resizes user-selected pictures and writes PNGs with full alpha channel.
    4. Automatically supplies default assets for any unassigned pieces.
    5. Sets up the Boards directory with DefaultBoard.png (or custom board).
    6. Copies theme sounds for full audio support.
    
    Returns (success: bool, message: str).
    """
    clean_name = sanitize_pack_name(pack_name)
    if not clean_name:
        return False, "Pack name cannot be empty or contain illegal characters."

    if clean_name.lower() == "default":
        return False, "Cannot overwrite the default base theme."

    pack_dir = Assets.ASSET_PACKS_DIR / clean_name
    boards_dir = pack_dir / "Boards"
    pieces_dir = pack_dir / "pieces"
    sounds_dir = pack_dir / "sounds"

    try:
        boards_dir.mkdir(parents=True, exist_ok=True)
        pieces_dir.mkdir(parents=True, exist_ok=True)

        default_pack_dir = Assets.ASSET_PACKS_DIR / "Default"

        # 1. Save or copy board image
        if custom_board_path and os.path.isfile(custom_board_path):
            board_surf = pygame.image.load(custom_board_path).convert()
            board_scaled = pygame.transform.smoothscale(board_surf, (Assets.BOARD_WIDTH, Assets.BOARD_HEIGHT))
            pygame.image.save(board_scaled, str(boards_dir / "DefaultBoard.png"))
        else:
            default_board = default_pack_dir / "Boards" / "DefaultBoard.png"
            if default_board.is_file():
                shutil.copy(default_board, boards_dir / "DefaultBoard.png")
            else:
                # Procedural board fallback
                board_surf = pygame.Surface((Assets.BOARD_WIDTH, Assets.BOARD_HEIGHT))
                board_surf.fill((235, 235, 235))
                pygame.image.save(board_surf, str(boards_dir / "DefaultBoard.png"))

        # 2. Save and resize piece images
        for spec in PIECE_SPECS:
            code = spec["code"]
            filename = spec["file"]
            dest_file = pieces_dir / filename

            # Case A: User chose a custom local picture for this piece
            if code in piece_paths and os.path.isfile(piece_paths[code]):
                raw_surf = pygame.image.load(piece_paths[code]).convert_alpha()
                # Target save dimension: proportional fit inside high-res square box (160x160)
                # This ensures the piece fits cleanly inside board squares without cropping
                target_size = (
                    int(spec["size"][0] * 1.8),
                    int(spec["size"][1] * 1.8),
                )
                fitted_surf = resize_image_for_board(raw_surf, target_size)
                pygame.image.save(fitted_surf, str(dest_file))

            # Case B: Unassigned piece -> copy default piece image
            else:
                default_file = Assets.resolve_file_case_insensitive(default_pack_dir / "pieces", filename)
                if default_file and default_file.is_file():
                    shutil.copy(default_file, dest_file)
                elif default_piece_images and code in default_piece_images:
                    pygame.image.save(default_piece_images[code], str(dest_file))

        # 3. Copy sounds from default pack if available
        default_sounds = default_pack_dir / "sounds"
        if default_sounds.is_dir():
            shutil.copytree(default_sounds, sounds_dir, dirs_exist_ok=True)

        return True, f"Asset pack '{clean_name}' created successfully!"

    except Exception as err:
        return False, f"Failed to save asset pack: {err}"


class AssetPackCreatorState:
    """
    Manages interactive state for the Asset Pack Creator panel.
    Tracks user input pack name, piece-by-piece file selections, thumbnail previews,
    and handles validation and creation triggers.
    """

    def __init__(self):
        self.pack_name: str = "CustomTheme"
        self.name_focused: bool = False
        self.cursor_timer: float = 0.0
        self.cursor_visible: bool = True

        # Mapping: piece_code -> chosen local image file path
        self.piece_paths: Dict[str, str] = {}
        # Mapping: piece_code -> loaded 52x52 pygame.Surface thumbnail preview
        self.preview_surfaces: Dict[str, pygame.Surface] = {}

        self.custom_board_path: Optional[str] = None
        self.status_message: str = "Select a picture for each piece, or fill remaining with default."
        self.status_is_error: bool = False

    def reset(self, default_piece_images: Optional[Dict[str, pygame.Surface]] = None) -> None:
        """Reset creator state to defaults."""
        self.pack_name = "CustomTheme"
        self.name_focused = False
        self.piece_paths.clear()
        self.preview_surfaces.clear()
        self.custom_board_path = None
        self.status_message = "Select a picture for each piece, or fill remaining with default."
        self.status_is_error = False

        # Pre-populate preview surfaces with default pack images
        if default_piece_images:
            for spec in PIECE_SPECS:
                code = spec["code"]
                if code in default_piece_images:
                    img = default_piece_images[code]
                    self.preview_surfaces[code] = pygame.transform.smoothscale(img, (48, 48))

    def set_piece_image(self, code: str, file_path: str) -> bool:
        """Assign a chosen image to a piece code and generate preview thumbnail."""
        if not os.path.isfile(file_path):
            self.status_message = f"File not found: {file_path}"
            self.status_is_error = True
            return False

        try:
            surf = pygame.image.load(file_path).convert_alpha()
            self.piece_paths[code] = file_path
            # Generate crisp 48x48 preview thumbnail
            scaled_preview = resize_image_for_board(surf, (48, 48))
            self.preview_surfaces[code] = scaled_preview
            spec = SPEC_BY_CODE.get(code, {})
            name = spec.get("name", code)
            self.status_message = f"Selected image for {name}"
            self.status_is_error = False
            return True
        except Exception as err:
            self.status_message = f"Error loading image: {err}"
            self.status_is_error = True
            return False

    def clear_piece_image(self, code: str, default_piece_images: Optional[Dict[str, pygame.Surface]] = None) -> None:
        """Revert a piece's custom image back to the default pack image."""
        if code in self.piece_paths:
            del self.piece_paths[code]
        if default_piece_images and code in default_piece_images:
            self.preview_surfaces[code] = pygame.transform.smoothscale(default_piece_images[code], (48, 48))
        elif code in self.preview_surfaces:
            del self.preview_surfaces[code]
        spec = SPEC_BY_CODE.get(code, {})
        name = spec.get("name", code)
        self.status_message = f"Reverted {name} to default"
        self.status_is_error = False

    def browse_for_piece(self, code: str) -> None:
        """Open the OS file dialog for a specific piece."""
        spec = SPEC_BY_CODE.get(code, {})
        name = spec.get("name", "Piece")
        path = open_file_dialog_for_image(title=f"Choose Image for {name}")
        if path:
            self.set_piece_image(code, path)

    def browse_folder_and_auto_match(self) -> None:
        """
        Open folder picker and automatically match filenames inside to piece codes.
        Recursively scans the folder (including white/, black/, pieces/ subdirectories),
        matching all standard chess naming conventions.
        """
        folder = open_folder_dialog(title="Select Folder Containing Piece Images")
        if not folder or not os.path.isdir(folder):
            return

        folder_path = Path(folder)
        extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

        # Collect all image files recursively across top-level and subdirectories
        all_image_files: List[Path] = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in extensions:
                    all_image_files.append(p)

        if not all_image_files:
            self.status_message = "No image files (.png, .jpg, .webp) found in selected folder."
            self.status_is_error = True
            return

        # Pre-set pack name to folder name if still using placeholder default
        if self.pack_name in ("CustomTheme", "") and folder_path.name:
            clean_dir = sanitize_pack_name(folder_path.name)
            if clean_dir and clean_dir.lower() != "default":
                self.pack_name = clean_dir

        # Check for board image in folder
        for f in all_image_files:
            stem = f.stem.lower()
            if any(b_name in stem for b_name in ("board", "chessboard", "defaultboard")):
                self.custom_board_path = str(f)
                break

        matched_count = 0
        matched_codes = set()

        for f in all_image_files:
            code = match_piece_file(f, siblings=all_image_files)
            if code and code in SPEC_BY_CODE and code not in matched_codes:
                if self.set_piece_image(code, str(f)):
                    matched_codes.add(code)
                    matched_count += 1

        if matched_count == 12:
            self.status_message = f"Perfect match! All 12 pieces imported from '{folder_path.name}'."
            self.status_is_error = False
        elif matched_count > 0:
            missing_names = [s["name"] for s in PIECE_SPECS if s["code"] not in matched_codes]
            missing_str = ", ".join(missing_names[:3])
            if len(missing_names) > 3:
                missing_str += f" (+{len(missing_names) - 3} more)"
            self.status_message = f"Imported {matched_count}/12 pieces! Missing: {missing_str}."
            self.status_is_error = False
        else:
            self.status_message = "Could not identify piece names in selected folder."
            self.status_is_error = True

    def update(self, dt: float) -> None:
        """Update cursor blink timer."""
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0.0
            self.cursor_visible = not self.cursor_visible

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """
        Handle text input when typing pack name.
        Returns True if the event was consumed.
        """
        if not self.name_focused:
            return False

        if event.key == pygame.K_BACKSPACE:
            self.pack_name = self.pack_name[:-1]
            return True
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.name_focused = False
            return True
        elif event.key == pygame.K_ESCAPE:
            self.name_focused = False
            return True
        elif event.unicode and len(event.unicode) == 1:
            # Allow alphanumeric, underscore, hyphen, space
            char = event.unicode
            if (char.isalnum() or char in ("_", "-", " ")) and len(self.pack_name) < 24:
                self.pack_name += char
                return True

        return False

    @property
    def custom_count(self) -> int:
        """Number of pieces customized with local device images."""
        return len(self.piece_paths)

