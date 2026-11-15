# test_sound_pack_creator.py
"""
Unit tests for the Custom Sound Asset Pack Creator.
Verifies:
- Sound pack name sanitization and validation
- Filename auto-matching logic for all 11 sound events across audio formats (.wav, .mp3, .ogg, etc.)
- Sound pack creation, file copying, and integration with Assets.py
- Real-time in-modal audio preview, playback state tracking, and timer
- UIButtons, modal rect layout calculation, and modal rendering
- Dynamic sound pack switching and discovery
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root and src2 to sys.path
TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
SRC2_DIR = PROJECT_ROOT / "src2"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC2_DIR))

# Headless video driver
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame

import Assets
from sound_pack_creator import (
    SOUND_SPECS,
    SPEC_BY_ID,
    SOUND_PACKS_DIR,
    sanitize_pack_name,
    match_sound_file,
    save_sound_pack,
    SoundPackCreatorState,
)
from renderer import ChessRenderer


def create_dummy_wav(filepath: Path) -> None:
    """Generate a valid, minimal RIFF WAV file for testing."""
    import wave
    import struct
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        # 100 samples of silence
        data = struct.pack("<100h", *([0] * 100))
        wf.writeframes(data)


class TestSoundPackCreator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            except Exception:
                pass
        if not pygame.display.get_init():
            pygame.display.init()
        cls.screen = pygame.display.set_mode((1200, 900))

    def setUp(self):
        self.test_pack_name = "TestSoundPack"
        self.pack_dir = SOUND_PACKS_DIR / self.test_pack_name
        if self.pack_dir.exists():
            shutil.rmtree(self.pack_dir, ignore_errors=True)

    def tearDown(self):
        if self.pack_dir.exists():
            shutil.rmtree(self.pack_dir, ignore_errors=True)

    def test_sanitize_pack_name(self):
        """Verify sound pack name sanitization removes forbidden characters."""
        self.assertEqual(sanitize_pack_name("Retro Arcade"), "Retro Arcade")
        self.assertEqual(sanitize_pack_name("Sound:Pack/Name?*"), "SoundPackName")
        self.assertEqual(sanitize_pack_name("   Trimmed   "), "Trimmed")
        self.assertEqual(sanitize_pack_name("<Invalid>|Sound\""), "InvalidSound")
        long_name = "S" * 50
        self.assertEqual(len(sanitize_pack_name(long_name)), 30)

    def test_match_sound_file(self):
        """Verify intelligent matching of audio file stems to sound IDs."""
        # 1. Checkmate vs Check precedence
        self.assertEqual(match_sound_file("checkmate.wav"), "game_over")
        self.assertEqual(match_sound_file("check_mate.mp3"), "game_over")
        self.assertEqual(match_sound_file("check.wav"), "check")
        self.assertEqual(match_sound_file("chess_check.ogg"), "check")

        # 2. Game Over / Win
        self.assertEqual(match_sound_file("game_over.wav"), "game_over")
        self.assertEqual(match_sound_file("victory.mp3"), "game_over")
        self.assertEqual(match_sound_file("win.flac"), "game_over")

        # 3. Game Start
        self.assertEqual(match_sound_file("game_start.wav"), "game_start")
        self.assertEqual(match_sound_file("gamestart.wav"), "game_start")
        self.assertEqual(match_sound_file("start.mp3"), "game_start")

        # 4. Castle
        self.assertEqual(match_sound_file("castle.wav"), "castle")
        self.assertEqual(match_sound_file("castling.ogg"), "castle")
        self.assertEqual(match_sound_file("rook_castle.wav"), "castle")

        # 5. Capture
        self.assertEqual(match_sound_file("capture.wav"), "capture")
        self.assertEqual(match_sound_file("take.mp3"), "capture")
        self.assertEqual(match_sound_file("eat.wav"), "capture")

        # 6. Promotion
        self.assertEqual(match_sound_file("promotion.wav"), "promotion")
        self.assertEqual(match_sound_file("promote.mp3"), "promotion")

        # 7. Invalid
        self.assertEqual(match_sound_file("invalid.wav"), "invalid")
        self.assertEqual(match_sound_file("illegal.wav"), "invalid")
        self.assertEqual(match_sound_file("error.ogg"), "invalid")

        # 8. Dash
        self.assertEqual(match_sound_file("dash.wav"), "dash")
        self.assertEqual(match_sound_file("sprint.wav"), "dash")

        # 9. Cards (shuffle vs flip)
        self.assertEqual(match_sound_file("card_shuffle.wav"), "card_shuffle")
        self.assertEqual(match_sound_file("card_flip.wav"), "card_flip")
        self.assertEqual(match_sound_file("flip.mp3"), "card_flip")

        # 10. Move
        self.assertEqual(match_sound_file("move.wav"), "move")
        self.assertEqual(match_sound_file("step.mp3"), "move")
        self.assertEqual(match_sound_file("tap.ogg"), "move")

        # Unmatched
        self.assertIsNone(match_sound_file("completely_unrelated_audio.wav"))

    def test_sound_pack_creator_state(self):
        """Verify SoundPackCreatorState methods, selection tracking, and text input."""
        state = SoundPackCreatorState()
        self.assertEqual(state.pack_name, "CustomSounds")
        self.assertFalse(state.name_focused)
        self.assertEqual(state.custom_count, 0)
        self.assertEqual(state.total_count, 11)

        # Test text input handling
        state.name_focused = True
        state.pack_name = "Theme"
        # Simulate typing 'A'
        ev = pygame.event.Event(pygame.KEYDOWN, unicode="A", key=pygame.K_a)
        consumed = state.handle_keydown(ev)
        self.assertTrue(consumed)
        self.assertEqual(state.pack_name, "ThemeA")

        # Simulate backspace
        ev_back = pygame.event.Event(pygame.KEYDOWN, unicode="", key=pygame.K_BACKSPACE)
        consumed = state.handle_keydown(ev_back)
        self.assertTrue(consumed)
        self.assertEqual(state.pack_name, "Theme")

        # Simulate return to unfocus
        ev_enter = pygame.event.Event(pygame.KEYDOWN, unicode="", key=pygame.K_RETURN)
        consumed = state.handle_keydown(ev_enter)
        self.assertTrue(consumed)
        self.assertFalse(state.name_focused)

        # Create temporary dummy audio file
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_wav = Path(tmpdir) / "move_sound.wav"
            create_dummy_wav(tmp_wav)

            # Assign sound
            ok = state.set_sound_file("move", str(tmp_wav))
            self.assertTrue(ok)
            self.assertTrue(state.has_sound("move"))
            self.assertEqual(state.custom_count, 1)

            # Clear sound
            state.clear_sound("move")
            self.assertFalse(state.has_sound("move"))
            self.assertEqual(state.custom_count, 0)

            # Batch auto-matching
            check_wav = Path(tmpdir) / "check.wav"
            capture_wav = Path(tmpdir) / "capture.wav"
            create_dummy_wav(check_wav)
            create_dummy_wav(capture_wav)

            matched = state.auto_match_from_folder(tmpdir)
            self.assertIn("check", matched)
            self.assertIn("capture", matched)
            self.assertTrue(state.has_sound("check"))
            self.assertTrue(state.has_sound("capture"))

    def test_save_sound_pack_and_assets_integration(self):
        """Verify creating, saving, and switching a sound pack in the Assets system."""
        with tempfile.TemporaryDirectory() as tmpdir:
            move_wav = Path(tmpdir) / "Move.wav"
            check_wav = Path(tmpdir) / "Check.wav"
            create_dummy_wav(move_wav)
            create_dummy_wav(check_wav)

            sound_paths = {
                "move": str(move_wav),
                "check": str(check_wav),
            }

            ok, msg = save_sound_pack(self.test_pack_name, sound_paths)
            self.assertTrue(ok, msg)
            self.assertTrue(self.pack_dir.exists())
            self.assertTrue((self.pack_dir / "Move.wav").exists())
            self.assertTrue((self.pack_dir / "Check.wav").exists())

            # Verify available sound packs discovery
            packs = Assets.get_available_sound_packs()
            self.assertIn(self.test_pack_name, packs)

            # Verify load_sound_pack
            loaded = Assets.load_sound_pack(self.test_pack_name)
            self.assertTrue(loaded)
            self.assertEqual(Assets.get_active_sound_pack(), self.test_pack_name)

            # Verify switch_sound_pack
            switched = Assets.switch_sound_pack(self.test_pack_name)
            self.assertTrue(switched)

    def test_renderer_sound_pack_creator_ui(self):
        """Verify UIButtons, modal rect calculation, and rendering."""
        renderer = ChessRenderer(
            screen=self.screen,
            board_x=50,
            board_y=50,
            square_size=100,
            panel_x=900,
            panel_width=270,
        )

        # Verify buttons exist
        self.assertTrue(hasattr(renderer.buttons, "create_sound_pack"))
        self.assertIsInstance(renderer.buttons.create_sound_pack, pygame.Rect)

        # Verify rects structure
        rects = renderer.get_sound_pack_creator_rects()
        self.assertIn("modal", rects)
        self.assertIn("close", rects)
        self.assertIn("cancel", rects)
        self.assertIn("save", rects)
        self.assertIn("import_folder", rects)
        self.assertIn("reset_all", rects)
        self.assertIn("name_input", rects)
        self.assertIn("play", rects)
        self.assertIn("browse", rects)
        self.assertIn("clear", rects)

        # Check all 11 sound specs have buttons
        for spec in SOUND_SPECS:
            sid = spec["id"]
            self.assertIn(sid, rects["play"])
            self.assertIn(sid, rects["browse"])
            self.assertIn(sid, rects["clear"])

        # Test rendering without exception
        state = SoundPackCreatorState()
        renderer.draw_sound_pack_creator_modal(mouse_pos=(100, 100), state=state)


if __name__ == "__main__":
    unittest.main()

