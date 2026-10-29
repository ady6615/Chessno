# test_ui_rendering.py
"""
Unit tests for ChessRenderer UI panel and mode rendering in Chessno.
Verifies that Classic mode draws clean FIDE rules and captured pieces
without any accidental card overlays or card placeholders.
"""

import os
import sys
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
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import chess

from game_engine import GameState, ClassicChessMode
from uno_engine import ChessUnoMode
from snail_engine import ImmortalSnailMode
from queen_pawn_engine import QueenPawnMode
from renderer import ChessRenderer
import Assets


class TestUIRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.board_img, cls.piece_images = Assets.load_assets("Default")
        cls.renderer = ChessRenderer(screen=cls.screen)

    def test_classic_mode_panel_rendering_no_captures(self):
        state = GameState(mode=ClassicChessMode())
        # Should render cleanly without error
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

    def test_classic_mode_panel_rendering_with_captures(self):
        state = GameState(mode=ClassicChessMode())
        # Make moves leading to captures
        state.make_move(chess.E2, chess.E4)
        state.make_move(chess.D7, chess.D5)
        res = state.make_move(chess.E4, chess.D5)  # White captures Black pawn
        self.assertTrue(res.is_capture)
        self.assertIn("bp", state.captured_pieces["w"])

        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

    def test_uno_mode_panel_rendering(self):
        state = GameState(mode=ChessUnoMode())
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

    def test_snail_mode_panel_rendering(self):
        state = GameState(mode=ImmortalSnailMode())
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

    def test_queen_pawn_mode_panel_rendering(self):
        state = GameState(mode=QueenPawnMode())
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
        )

    def test_mode_selector_modal_rendering(self):
        rects = self.renderer.draw_mode_selector_modal(mouse_pos=(600, 300))
        self.assertEqual(len(rects), 4)


if __name__ == "__main__":
    unittest.main()
