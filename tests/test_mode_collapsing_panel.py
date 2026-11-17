# test_mode_collapsing_panel.py
"""
Unit tests for the mode selecting collapsing panel in Chessno.
Tests collapsed state, hover-to-expand behavior, mini chips, mode card rects,
and rendering of all 9 modes without crowding.
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

from renderer import ChessRenderer
from timer import ChessTimer
from ai_bot import ChessBotController, BotDifficulty


class TestModeCollapsingPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.renderer = ChessRenderer(screen=cls.screen)

    def setUp(self):
        self.renderer.mode_panel_expanded = False
        self.renderer.mode_panel_anim_height = 56.0

    def test_mode_selector_box_rect_dimensions(self):
        """Collapsed box is compact (height 56) and expanded box is spacious (height 248)."""
        collapsed_r = self.renderer.get_mode_selector_box_rect(expanded=False)
        expanded_r = self.renderer.get_mode_selector_box_rect(expanded=True)

        self.assertEqual(collapsed_r.height, 56)
        self.assertEqual(expanded_r.height, 248)
        self.assertEqual(collapsed_r.x, expanded_r.x)
        self.assertEqual(collapsed_r.y, expanded_r.y)
        self.assertEqual(collapsed_r.width, expanded_r.width)
        self.assertGreater(collapsed_r.width, 900)

    def test_mini_chip_rects(self):
        """Collapsed bar provides 9 clickable mini chips corresponding to all 9 modes."""
        chips = self.renderer.get_mode_selector_mini_chip_rects()
        self.assertEqual(len(chips), 9)
        expected_modes = [
            "Classic",
            "Chess + UNO",
            "Immortal Snail",
            "Queen Pawn",
            "Rook Dash",
            "Bishop Dash",
            "Hero Mode",
            "Atomic Chess",
            "Crazyhouse",
        ]
        collapsed_box = self.renderer.get_mode_selector_box_rect(expanded=False)
        for (chip_r, m_name), exp_name in zip(chips, expected_modes):
            self.assertEqual(m_name, exp_name)
            self.assertGreater(chip_r.width, 0)
            self.assertGreater(chip_r.height, 0)
            # Chip must be inside the collapsed box vertically
            self.assertGreaterEqual(chip_r.y, collapsed_box.y)
            self.assertLessEqual(chip_r.bottom, collapsed_box.bottom)

    def test_9_mode_card_rects_and_rows(self):
        """Expanded panel returns 9 mode card rects arranged in 2 balanced rows."""
        rects = self.renderer.get_mode_selector_rects()
        self.assertEqual(len(rects), 9)

        # Row 1 (cards 0 to 4): All share the same Y position
        row1 = rects[:5]
        row1_y = row1[0].y
        for r in row1:
            self.assertEqual(r.y, row1_y)
            self.assertGreater(r.width, 180)  # Much wider than previous 114px
            self.assertGreater(r.height, 80)

        # Row 2 (cards 5 to 8): All share the same Y position below Row 1
        row2 = rects[5:]
        row2_y = row2[0].y
        self.assertGreater(row2_y, row1[0].bottom)
        for r in row2:
            self.assertEqual(r.y, row2_y)
            self.assertGreater(r.width, 180)
            self.assertGreater(r.height, 80)

        # No overlapping cards within each row
        for i in range(len(row1) - 1):
            self.assertLessEqual(row1[i].right, row1[i + 1].x)
        for i in range(len(row2) - 1):
            self.assertLessEqual(row2[i].right, row2[i + 1].x)

    def test_modal_rendering_collapsed_when_mouse_away(self):
        """When mouse cursor is away, modal renders with mode panel collapsed."""
        mouse_pos = (600, 600)  # Away from mode panel (which is around y=86..142)
        timer = ChessTimer(time_limit_seconds=300)
        bot = ChessBotController(difficulty=BotDifficulty.CASUAL)

        ret = self.renderer.draw_mode_selector_modal(
            mouse_pos=mouse_pos,
            timer=timer,
            bot_controller=bot,
            current_mode_name="Crazyhouse",
        )
        self.assertEqual(len(ret), 8)
        self.assertFalse(self.renderer.mode_panel_expanded)

    def test_modal_rendering_expands_when_cursor_moves_over_it(self):
        """When mouse cursor moves over the mode panel, it expands dynamically."""
        collapsed_box = self.renderer.get_mode_selector_box_rect(expanded=False)
        # Position cursor inside the collapsed box
        mouse_pos = (collapsed_box.centerx, collapsed_box.centery)

        timer = ChessTimer(time_limit_seconds=300)
        bot = ChessBotController(difficulty=BotDifficulty.CASUAL)

        ret = self.renderer.draw_mode_selector_modal(
            mouse_pos=mouse_pos,
            timer=timer,
            bot_controller=bot,
            current_mode_name="Classic",
        )
        self.assertEqual(len(ret), 8)
        self.assertTrue(self.renderer.mode_panel_expanded)
        self.assertGreater(self.renderer.mode_panel_anim_height, 56.0)

    def test_all_modes_render_without_crash(self):
        """All 9 modes render cleanly in both collapsed and expanded states."""
        modes = [
            "Classic",
            "Chess + UNO",
            "Immortal Snail",
            "Queen Pawn",
            "Rook Dash",
            "Bishop Dash",
            "Hero Mode",
            "Atomic Chess",
            "Crazyhouse",
        ]
        timer = ChessTimer(time_limit_seconds=600)
        bot = ChessBotController(difficulty=BotDifficulty.MASTER)

        for mode_name in modes:
            # Collapsed test
            self.renderer.mode_panel_expanded = False
            self.renderer.mode_panel_anim_height = 56.0
            self.renderer.draw_mode_selector_modal(
                mouse_pos=(100, 800),
                timer=timer,
                bot_controller=bot,
                current_mode_name=mode_name,
            )

            # Expanded test
            self.renderer.mode_panel_expanded = True
            self.renderer.mode_panel_anim_height = 248.0
            self.renderer.draw_mode_selector_modal(
                mouse_pos=(600, 160),
                timer=timer,
                bot_controller=bot,
                current_mode_name=mode_name,
            )


if __name__ == "__main__":
    unittest.main()
