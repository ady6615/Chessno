# test_asset_pack_creator.py
"""
Unit tests for the Custom Asset Pack Creator.
Verifies:
- Name sanitization and validation
- Aspect-ratio preserving image scaling for board squares
- Full asset pack directory creation, file saving, and fallback population
- Discovery and loading of custom asset packs by the Assets system
- Interactive creator state tracking (piece selection, clearing, keyboard input)
- UI buttons, modal rect calculation, and rendering
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
import chess

import Assets
from coordinates import BOARD_SIZE
from asset_pack_creator import (
    PIECE_SPECS,
    WHITE_SPECS,
    BLACK_SPECS,
    SPEC_BY_CODE,
    sanitize_pack_name,
    resize_image_for_board,
    save_asset_pack,
    AssetPackCreatorState,
)
from renderer import ChessRenderer
from game_engine import GameState, ClassicChessMode


class TestAssetPackCreator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()
        # Ensure a dummy screen surface for rendering tests
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.board_img, cls.piece_images = Assets.load_assets()

    def setUp(self):
        self.test_pack_name = "TestCustomPack123"
        self.pack_dir = Assets.ASSET_PACKS_DIR / self.test_pack_name
        # Clean up any leftover test pack
        if self.pack_dir.exists():
            shutil.rmtree(self.pack_dir, ignore_errors=True)

    def tearDown(self):
        # Clean up test pack after each test
        if self.pack_dir.exists():
            shutil.rmtree(self.pack_dir, ignore_errors=True)

    def test_sanitize_pack_name(self):
        """Verify name sanitization removes illegal filesystem characters."""
        self.assertEqual(sanitize_pack_name("My Theme"), "My Theme")
        self.assertEqual(sanitize_pack_name("Test:Pack/Name?*"), "TestPackName")
        self.assertEqual(sanitize_pack_name("   Trimmed   "), "Trimmed")
        self.assertEqual(sanitize_pack_name("<Invalid>|Theme\""), "InvalidTheme")
        # Length truncation (max 30)
        long_name = "A" * 50
        self.assertEqual(len(sanitize_pack_name(long_name)), 30)

    def test_resize_image_for_board_aspect_ratio(self):
        """Verify aspect ratio is preserved when resizing images for board squares."""
        # Test wide surface (200x100 -> ratio 2:1)
        wide_surf = pygame.Surface((200, 100), pygame.SRCALPHA)
        wide_surf.fill((255, 0, 0, 255))
        resized_wide = resize_image_for_board(wide_surf, target_max=(160, 160))
        rw, rh = resized_wide.get_size()
        self.assertEqual(rw, 160)
        self.assertEqual(rh, 80)

        # Test tall surface (100x200 -> ratio 1:2)
        tall_surf = pygame.Surface((100, 200), pygame.SRCALPHA)
        tall_surf.fill((0, 255, 0, 255))
        resized_tall = resize_image_for_board(tall_surf, target_max=(160, 160))
        tw, th = resized_tall.get_size()
        self.assertEqual(tw, 80)
        self.assertEqual(th, 160)

        # Test square surface
        sq_surf = pygame.Surface((300, 300), pygame.SRCALPHA)
        resized_sq = resize_image_for_board(sq_surf, target_max=(120, 120))
        self.assertEqual(resized_sq.get_size(), (120, 120))

    def test_save_asset_pack_and_assets_system_integration(self):
        """Verify saving creates valid folder structure immediately discoverable by Assets."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a sample custom image for White King (wa) and Black Queen (bq)
            sample_king = tmp_path / "custom_king.png"
            sample_queen = tmp_path / "custom_queen.png"

            s_king = pygame.Surface((100, 100), pygame.SRCALPHA)
            s_king.fill((255, 215, 0, 255))
            pygame.image.save(s_king, str(sample_king))

            s_queen = pygame.Surface((120, 90), pygame.SRCALPHA)
            s_queen.fill((180, 50, 220, 255))
            pygame.image.save(s_queen, str(sample_queen))

            piece_paths = {
                "wa": str(sample_king),
                "bq": str(sample_queen),
            }

            ok, msg = save_asset_pack(
                pack_name=self.test_pack_name,
                piece_paths=piece_paths,
                default_piece_images=self.piece_images,
            )
            self.assertTrue(ok, f"save_asset_pack failed: {msg}")
            self.assertTrue(self.pack_dir.exists())
            self.assertTrue((self.pack_dir / "Boards" / "DefaultBoard.png").exists())
            self.assertTrue((self.pack_dir / "pieces").exists())

            # Verify all 12 piece files exist in the saved pack
            for spec in PIECE_SPECS:
                piece_file = self.pack_dir / "pieces" / spec["file"]
                self.assertTrue(piece_file.exists(), f"Missing piece file: {spec['file']}")

            # Verify Assets system discovers the new pack
            available = Assets.get_available_packs()
            self.assertIn(self.test_pack_name, available)

            # Verify Assets system can switch to and load the new pack
            new_board, new_pieces = Assets.switch_asset_pack(self.test_pack_name)
            self.assertIsNotNone(new_board)
            self.assertEqual(len(new_pieces), 12)
            self.assertIn("wa", new_pieces)
            self.assertIn("bq", new_pieces)

            # Revert to Default pack
            Assets.switch_asset_pack("Default")

    def test_save_asset_pack_validation(self):
        """Verify save_asset_pack rejects invalid names like 'Default' or empty string."""
        ok, msg = save_asset_pack("Default", {})
        self.assertFalse(ok)
        self.assertIn("Cannot overwrite", msg)

        ok, msg = save_asset_pack("   ", {})
        self.assertFalse(ok)
        self.assertIn("cannot be empty", msg)

    def test_creator_state_piece_assignment_and_clearing(self):
        """Verify state handles setting and clearing piece images with thumbnail generation."""
        state = AssetPackCreatorState()
        state.reset(default_piece_images=self.piece_images)

        self.assertEqual(state.custom_count, 0)
        self.assertEqual(len(state.preview_surfaces), 12)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            temp_img_path = tf.name

        try:
            sample_surf = pygame.Surface((150, 150), pygame.SRCALPHA)
            sample_surf.fill((50, 150, 250, 255))
            pygame.image.save(sample_surf, temp_img_path)

            # Set custom image for White Knight (wk)
            success = state.set_piece_image("wk", temp_img_path)
            self.assertTrue(success)
            self.assertEqual(state.custom_count, 1)
            self.assertIn("wk", state.piece_paths)
            self.assertIn("wk", state.preview_surfaces)

            # Clear piece image
            state.clear_piece_image("wk", default_piece_images=self.piece_images)
            self.assertEqual(state.custom_count, 0)
            self.assertNotIn("wk", state.piece_paths)
        finally:
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

    def test_creator_state_keydown_handling(self):
        """Verify text typing, backspace, and focus behavior."""
        state = AssetPackCreatorState()
        state.pack_name = "MyPack"
        state.name_focused = False

        # Event ignored when not focused
        event_a = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a, "unicode": "a"})
        consumed = state.handle_keydown(event_a)
        self.assertFalse(consumed)
        self.assertEqual(state.pack_name, "MyPack")

        # Focus and type 'X'
        state.name_focused = True
        event_x = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_x, "unicode": "X"})
        consumed = state.handle_keydown(event_x)
        self.assertTrue(consumed)
        self.assertEqual(state.pack_name, "MyPackX")

        # Backspace
        event_bk = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_BACKSPACE, "unicode": ""})
        consumed = state.handle_keydown(event_bk)
        self.assertTrue(consumed)
        self.assertEqual(state.pack_name, "MyPack")

        # Return blurs focus
        event_ret = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": ""})
        consumed = state.handle_keydown(event_ret)
        self.assertTrue(consumed)
        self.assertFalse(state.name_focused)

    def test_renderer_ui_buttons_and_modal_rects(self):
        """Verify UIButtons has create_pack and get_asset_pack_creator_rects provides all required targets."""
        renderer = ChessRenderer(
            screen=self.screen,
            board_x=50,
            board_y=50,
            square_size=100,
            panel_x=900,
            panel_width=270,
        )

        self.assertTrue(hasattr(renderer.buttons, "create_pack"))
        self.assertIsInstance(renderer.buttons.create_pack, pygame.Rect)

        rects = renderer.get_asset_pack_creator_rects()
        self.assertIn("modal", rects)
        self.assertIn("close", rects)
        self.assertIn("name_input", rects)
        self.assertIn("import_folder", rects)
        self.assertIn("reset_all", rects)
        self.assertIn("browse", rects)
        self.assertIn("clear", rects)
        self.assertIn("cards", rects)
        self.assertIn("status", rects)
        self.assertIn("cancel", rects)
        self.assertIn("save", rects)

        # Check all 12 pieces are present in browse, clear, and cards
        for spec in PIECE_SPECS:
            code = spec["code"]
            self.assertIn(code, rects["browse"])
            self.assertIn(code, rects["clear"])
            self.assertIn(code, rects["cards"])

    def test_renderer_draw_panel_and_creator_modal(self):
        """Verify draw_panel and draw_asset_pack_creator_modal render cleanly without error."""
        renderer = ChessRenderer(
            screen=self.screen,
            board_x=50,
            board_y=50,
            square_size=100,
            panel_x=900,
            panel_width=270,
        )
        state = GameState(mode=ClassicChessMode())
        creator_state = AssetPackCreatorState()
        creator_state.reset(default_piece_images=self.piece_images)

        # Render panel
        renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 310),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

        # Render creator modal
        rects = renderer.draw_asset_pack_creator_modal(
            mouse_pos=(400, 300),
            state=creator_state,
            default_piece_images=self.piece_images,
        )
        self.assertIsNotNone(rects)
        self.assertIn("save", rects)


if __name__ == "__main__":
    unittest.main()
