# sound_pack_creator.py
"""
Sound Asset Pack Creator for Chessno.

Allows users to:
1. Name their custom sound asset pack (e.g. 'RetroArcade', 'EpicOrchestral').
2. Choose audio files from their local device one-by-one for each sound event
   (Check, Checkmate/Game Over, Move, Capture, Castle, Promotion, etc.).
3. Test and preview each sound directly inside the panel with a single click.
4. Batch-import sound files from a local directory with intelligent name auto-matching.
5. Store the sound pack locally under the assets system so it is immediately
   playable and accessible in-game.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import os
import re
import shutil
import pygame

import Assets

# Full specification of all in-game sound events
SOUND_SPECS: List[Dict[str, Any]] = [
    {
        "id": "check",
        "name": "Check Sound",
        "file": "Check.wav",
        "category": "Tactical / Alerts",
        "desc": "Played when a King is in check",
        "icon": "⚠️",
    },
    {
        "id": "game_over",
        "name": "Checkmate / Game Over",
        "file": "GameOver.wav",
        "category": "Game State",
        "desc": "Played on checkmate, stalemate, or win",
        "icon": "🏆",
    },
    {
        "id": "move",
        "name": "Move Sound",
        "file": "Move.wav",
        "category": "Gameplay",
        "desc": "Played on standard piece movement",
        "icon": "♟️",
    },
    {
        "id": "capture",
        "name": "Capture Sound",
        "file": "Capture.wav",
        "category": "Gameplay",
        "desc": "Played when capturing an opponent piece",
        "icon": "⚔️",
    },
    {
        "id": "castle",
        "name": "Castle Sound",
        "file": "Castle.wav",
        "category": "Gameplay",
        "desc": "Played on kingside or queenside castling",
        "icon": "🏰",
    },
    {
        "id": "promotion",
        "name": "Pawn Promotion Sound",
        "file": "Promotion.wav",
        "category": "Tactical / Alerts",
        "desc": "Played when a pawn promotes on the 8th rank",
        "icon": "👑",
    },
    {
        "id": "game_start",
        "name": "Game Start Sound",
        "file": "GameStart.wav",
        "category": "Game State",
        "desc": "Played when starting or restarting a match",
        "icon": "🏁",
    },
    {
        "id": "invalid",
        "name": "Invalid Move Sound",
        "file": "Invalid.wav",
        "category": "Gameplay",
        "desc": "Played when attempting an illegal move",
        "icon": "🚫",
    },
    {
        "id": "dash",
        "name": "Dash Sprint Sound",
        "file": "Dash.wav",
        "category": "Special Modes",
        "desc": "Played in Rook Dash and Bishop Dash",
        "icon": "⚡",
    },
    {
        "id": "card_flip",
        "name": "Card Flip Sound",
        "file": "CardFlip.wav",
        "category": "Special Modes",
        "desc": "Played when drawing/flipping a card in Chess + UNO",
        "icon": "🃏",
    },
    {
        "id": "card_shuffle",
        "name": "Card Shuffle Sound",
        "file": "CardShuffle.wav",
        "category": "Special Modes",
        "desc": "Played when shuffling the UNO card deck",
        "icon": "🔀",
    },
]

SPEC_BY_ID = {s["id"]: s for s in SOUND_SPECS}

# Directory where standalone custom sound packs are stored
SOUND_PACKS_DIR = Assets.ASSET_PACKS_DIR / "sound_packs"


def sanitize_pack_name(name: str) -> str:
    """Sanitize user input to create a safe, valid directory name."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean[:30]


def open_file_dialog_for_sound(title: str = "Select Sound File") -> Optional[str]:
    """
    Open native OS file picker to let the user select an audio file from their device.
    Supports WAV, MP3, OGG, FLAC, and common audio formats.
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
                ("Audio files", "*.wav;*.mp3;*.ogg;*.flac;*.aac;*.wma;*.aiff"),
                ("WAV audio", "*.wav"),
                ("MP3 audio", "*.mp3"),
                ("OGG audio", "*.ogg"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return file_path if file_path else None
    except Exception as err:
        print(f"Warning: Could not open sound file dialog: {err}")
        return None


def open_folder_dialog_for_sounds(title: str = "Select Folder Containing Sound Files") -> Optional[str]:
    """Open native OS directory picker for convenient batch sound importing."""
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


def match_sound_file(filepath: Any) -> Optional[str]:
    """
    Intelligently identify the sound event ID (e.g. 'check', 'game_over') from a file path.
    Supports standard filenames, colloquial names, and common variants:
    - Check: check.wav, king_check.mp3, check_alert.wav, etc.
    - Checkmate / Game Over: checkmate.wav, game_over.mp3, win.wav, victory.wav, mate.wav, etc.
    - Move: move.wav, piece_move.mp3, tap.wav, step.wav, etc.
    - Capture: capture.wav, take.mp3, kill.wav, hit.wav, strike.wav, etc.
    - Castle: castle.wav, castling.mp3, rooking.wav, etc.
    - Promotion: promotion.wav, promote.mp3, queening.wav, upgrade.wav, etc.
    - Game Start: gamestart.wav, start.mp3, begin.wav, intro.wav, etc.
    - Invalid: invalid.wav, illegal.mp3, error.wav, buzzer.wav, wrong.wav, etc.
    - Dash: dash.wav, sprint.mp3, whoosh.wav, speed.wav, etc.
    - Card Flip: cardflip.wav, flip.mp3, card.wav, etc.
    - Card Shuffle: cardshuffle.wav, shuffle.mp3, deck.wav, etc.
    """
    stem = Path(filepath).stem.lower()
    tokens = set(re.findall(r'[a-z0-9]+', stem))

    # 1. Checkmate / Game Over (Check checkmate before check!)
    if any(k in stem for k in ("checkmate", "game_over", "gameover", "victory", "winner", "win", "mate")):
        return "game_over"

    # 2. Check
    if any(k in stem for k in ("check", "alert")):
        return "check"

    # 3. Capture
    if any(k in stem for k in ("capture", "take", "strike", "hit", "kill", "attack")) or "eat" in tokens or "eaten" in tokens:
        return "capture"

    # 4. Castle
    if any(k in stem for k in ("castle", "castling", "rooking")):
        return "castle"

    # 5. Promotion
    if any(k in stem for k in ("promotion", "promote", "queening", "upgrade")):
        return "promotion"

    # 6. Game Start
    if any(k in stem for k in ("gamestart", "start", "begin", "intro", "new_game", "newgame")):
        return "game_start"

    # 7. Invalid / Illegal move
    if any(k in stem for k in ("invalid", "illegal", "error", "buzzer", "wrong", "denied")):
        return "invalid"

    # 8. Dash Sprint
    if any(k in stem for k in ("dash", "sprint", "whoosh", "speed")):
        return "dash"

    # 9. Card Shuffle (Check shuffle before card)
    if any(k in stem for k in ("shuffle", "cardshuffle", "card_shuffle", "deck")):
        return "card_shuffle"

    # 10. Card Flip
    if any(k in stem for k in ("cardflip", "card_flip", "flip", "card")):
        return "card_flip"

    # 11. Move Sound
    if any(k in stem for k in ("move", "step", "tap", "click", "slide")):
        return "move"

    return None


def save_sound_pack(
    pack_name: str,
    sound_paths: Dict[str, str],
    active_theme_name: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Assemble, validate, and save the custom sound asset pack to disk.
    
    1. Validates pack name and directory safety.
    2. Stores sound files in `src2/assets/sound_packs/<pack_name>/`.
    3. Also updates `src2/assets/<active_theme_name>/sounds/` so the active visual
       pack immediately plays the new custom audio.
    4. Automatically loads and activates the sound pack via `Assets.load_sound_pack`.
    
    Returns (success: bool, message: str).
    """
    clean_name = sanitize_pack_name(pack_name)
    if not clean_name:
        return False, "Sound pack name cannot be empty or contain illegal characters."

    if clean_name.lower() == "default":
        return False, "Cannot overwrite the default sound pack."

    try:
        SOUND_PACKS_DIR.mkdir(parents=True, exist_ok=True)
        pack_dir = SOUND_PACKS_DIR / clean_name
        pack_dir.mkdir(parents=True, exist_ok=True)

        # Copy user selected sound files into the pack directory
        for spec in SOUND_SPECS:
            sid = spec["id"]
            target_filename = spec["file"]
            dest_file = pack_dir / target_filename

            if sid in sound_paths and os.path.isfile(sound_paths[sid]):
                src_path = Path(sound_paths[sid])
                # Preserve file extension if not .wav
                if src_path.suffix.lower() != ".wav":
                    dest_file = pack_dir / f"{Path(target_filename).stem}{src_path.suffix.lower()}"
                shutil.copy(src_path, dest_file)

        # Also copy sounds into active theme's sounds folder if an active theme exists
        if active_theme_name:
            theme_sounds_dir = Assets.ASSET_PACKS_DIR / active_theme_name / "sounds"
            try:
                theme_sounds_dir.mkdir(parents=True, exist_ok=True)
                for f in pack_dir.iterdir():
                    if f.is_file():
                        shutil.copy(f, theme_sounds_dir / f.name)
            except Exception as err:
                print(f"Notice: Could not copy sounds to active theme: {err}")

        # Activate the newly created sound pack immediately
        Assets.load_sound_pack(clean_name)

        return True, f"Sound pack '{clean_name}' created and applied successfully!"

    except Exception as err:
        return False, f"Failed to save sound pack: {err}"


class SoundPackCreatorState:
    """
    Manages interactive state for the Sound Asset Pack Creator panel.
    Tracks user input pack name, sound file selections, cached Sound objects for
    instant in-modal audio preview, and handles validation and saving.
    """

    def __init__(self):
        self.pack_name: str = "CustomSounds"
        self.name_focused: bool = False
        self.cursor_timer: float = 0.0
        self.cursor_visible: bool = True

        # Mapping: sound_id -> chosen local audio file path
        self.sound_paths: Dict[str, str] = {}
        # Mapping: sound_id -> loaded pygame.mixer.Sound object
        self.sound_objects: Dict[str, pygame.mixer.Sound] = {}

        self.currently_playing_id: Optional[str] = None
        self.play_timer: float = 0.0
        self.status_message: str = "Choose an audio file for each sound event, or click 'Import Folder...'."
        self.status_is_error: bool = False

    def reset(self) -> None:
        """Reset creator state to defaults."""
        self.stop_preview()
        self.pack_name = "CustomSounds"
        self.name_focused = False
        self.sound_paths.clear()
        self.sound_objects.clear()
        self.currently_playing_id = None
        self.play_timer = 0.0
        self.status_message = "Choose an audio file for each sound event, or click 'Import Folder...'."
        self.status_is_error = False

    def has_sound(self, sound_id: str) -> bool:
        """Return True if the sound event has a custom audio file assigned."""
        return sound_id in self.sound_paths

    def set_sound_file(self, sound_id: str, file_path: str) -> bool:
        """Assign an audio file to a sound event and load it for instant preview."""
        if not os.path.isfile(file_path):
            self.status_message = f"File not found: {file_path}"
            self.status_is_error = True
            return False

        try:
            # Ensure audio mixer is initialized
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

            sound = pygame.mixer.Sound(file_path)
            sound.set_volume(0.85)

            self.sound_paths[sound_id] = file_path
            self.sound_objects[sound_id] = sound

            spec = SPEC_BY_ID.get(sound_id, {})
            name = spec.get("name", sound_id)
            self.status_message = f"Selected audio for {name}"
            self.status_is_error = False

            # Play a short preview immediately
            self.play_preview(sound_id)
            return True
        except Exception as err:
            self.status_message = f"Could not load audio file: {err}"
            self.status_is_error = True
            return False

    def clear_sound_file(self, sound_id: str) -> None:
        """Revert a sound event back to procedural/default tone."""
        if self.currently_playing_id == sound_id:
            self.stop_preview()
        if sound_id in self.sound_paths:
            del self.sound_paths[sound_id]
        if sound_id in self.sound_objects:
            del self.sound_objects[sound_id]

        spec = SPEC_BY_ID.get(sound_id, {})
        name = spec.get("name", sound_id)
        self.status_message = f"Reverted {name} to default tone"
        self.status_is_error = False

    clear_sound = clear_sound_file

    def play_preview(self, sound_id: str) -> bool:
        """
        Play audio preview for a sound event.
        Uses custom chosen audio if assigned, or falls back to current asset procedural sound.
        """
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

            # Stop any currently playing preview
            self.stop_preview()

            # Case A: User chose custom sound file
            if sound_id in self.sound_objects:
                sound = self.sound_objects[sound_id]
                sound.play()
                self.currently_playing_id = sound_id
                self.play_timer = 0.6
                return True

            # Case B: Procedural / default asset sound
            sound = Assets.get_sound(sound_id)
            if sound:
                sound.play()
                self.currently_playing_id = sound_id
                self.play_timer = 0.5
                return True

            return False
        except Exception as err:
            print(f"Warning: Could not play sound preview: {err}")
            return False

    def stop_preview(self) -> None:
        """Stop any playing sound preview."""
        self.currently_playing_id = None
        self.play_timer = 0.0

    def browse_for_sound(self, sound_id: str) -> None:
        """Open native OS file dialog for a specific sound event."""
        spec = SPEC_BY_ID.get(sound_id, {})
        name = spec.get("name", "Sound")
        path = open_file_dialog_for_sound(title=f"Choose Audio File for {name}")
        if path:
            self.set_sound_file(sound_id, path)

    def browse_folder_and_auto_match(self) -> None:
        """
        Open folder picker and automatically match audio filenames to sound IDs.
        Recursively scans the folder for .wav, .mp3, .ogg, .flac files.
        """
        folder = open_folder_dialog_for_sounds(title="Select Folder Containing Sound Files")
        if folder:
            self.auto_match_from_folder(folder)

    def auto_match_from_folder(self, folder: str) -> List[str]:
        """
        Scan a folder for audio files, auto-match them against sound events,
        load them for preview, and update status messages. Returns list of matched sound IDs.
        """
        if not folder or not os.path.isdir(folder):
            return []

        folder_path = Path(folder)
        extensions = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".wma", ".aiff"}

        all_audio_files: List[Path] = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in extensions:
                    all_audio_files.append(p)

        if not all_audio_files:
            self.status_message = "No audio files (.wav, .mp3, .ogg) found in selected folder."
            self.status_is_error = True
            return []

        # Pre-set pack name to folder name if still using placeholder default
        if self.pack_name in ("CustomSounds", "") and folder_path.name:
            clean_dir = sanitize_pack_name(folder_path.name)
            if clean_dir and clean_dir.lower() != "default":
                self.pack_name = clean_dir

        matched_count = 0
        matched_ids = set()

        for f in all_audio_files:
            sid = match_sound_file(f)
            if sid and sid in SPEC_BY_ID and sid not in matched_ids:
                if self.set_sound_file(sid, str(f)):
                    matched_ids.add(sid)
                    matched_count += 1

        if matched_count == len(SOUND_SPECS):
            self.status_message = f"Perfect match! All {matched_count} sounds imported from '{folder_path.name}'."
            self.status_is_error = False
        elif matched_count > 0:
            missing_names = [s["name"] for s in SOUND_SPECS if s["id"] not in matched_ids]
            missing_str = ", ".join(missing_names[:3])
            if len(missing_names) > 3:
                missing_str += f" (+{len(missing_names) - 3} more)"
            self.status_message = f"Imported {matched_count}/{len(SOUND_SPECS)} sounds! Missing: {missing_str}."
            self.status_is_error = False
        else:
            self.status_message = "Could not identify sound names in selected folder."
            self.status_is_error = True

        return list(matched_ids)

    def update(self, dt: float) -> None:
        """Update cursor blink timer and sound preview playback timer."""
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0.0
            self.cursor_visible = not self.cursor_visible

        if self.currently_playing_id:
            self.play_timer -= dt
            if self.play_timer <= 0.0:
                self.currently_playing_id = None

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """
        Handle text input when typing sound pack name.
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
            char = event.unicode
            if (char.isalnum() or char in ("_", "-", " ")) and len(self.pack_name) < 24:
                self.pack_name += char
                return True

        return False

    @property
    def custom_count(self) -> int:
        """Number of sound events customized with local device audio files."""
        return len(self.sound_paths)

    @property
    def total_count(self) -> int:
        """Total number of in-game sound events to configure."""
        return len(SOUND_SPECS)
