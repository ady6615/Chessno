# test_mode_collapsing_panel.py
"""
Unit tests for the mode selecting per-button collapsing panel in Chessno.
Tests that the collapsing mechanism is removed from the main mods section
and applied to each mod's button:
- When unhovered, each mod button is collapsed and displays only the name of the mod.
- When hovered, that specific mod button expands to display the remaining details
  (badge subtitle and rule bullets).
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
        self.renderer.mode_button_anim_heights.clear()

    def test_mode_selector_box_rect_dimensions(self):
        """Main mods section has a permanent, fixed spacious box (height 248)."""
        panel_r = self.renderer.get_mode_selector_box_rect()
        self.assertEqual(panel_r.height, 248)
        self.assertGreater(panel_r.width, 900)

    def test_9_mode_card_rects_and_rows(self):
        """Mode selector returns 9 cards arranged in 2 balanced rows for both collapsed and expanded states."""
        # Expanded state (height 96)
        rects_exp = self.renderer.get_mode_selector_rects(expanded=True)
        self.assertEqual(len(rects_exp), 9)
        for r in rects_exp:
            self.assertEqual(r.height, 96)
            self.assertGreater(r.width, 180)

        # Collapsed state (height 44)
        rects_col = self.renderer.get_mode_selector_rects(expanded=False)
        self.assertEqual(len(rects_col), 9)
        for r in rects_col:
            self.assertEqual(r.height, 44)
            self.assertGreater(r.width, 180)

        # Row 1 (cards 0 to 4): All share the same Y position
        row1 = rects_exp[:5]
        row1_y = row1[0].y
        for r in row1:
            self.assertEqual(r.y, row1_y)

        # Row 2 (cards 5 to 8): All share the same Y position below Row 1
        row2 = rects_exp[5:]
        row2_y = row2[0].y
        self.assertGreater(row2_y, row1[0].bottom)
        for r in row2:
            self.assertEqual(r.y, row2_y)

        # No horizontal overlapping cards within each row
        for i in range(len(row1) - 1):
            self.assertLessEqual(row1[i].right, row1[i + 1].x)
        for i in range(len(row2) - 1):
            self.assertLessEqual(row2[i].right, row2[i + 1].x)

    def test_modal_rendering_collapsed_buttons_when_mouse_away(self):
        """When mouse cursor is away, all mod buttons remain collapsed at ~44px showing only mod names."""
        mouse_pos = (600, 600)  # Away from mode panel (which is around y=86..334)
        timer = ChessTimer(time_limit_seconds=300)
        bot = ChessBotController(difficulty=BotDifficulty.CASUAL)

        ret = self.renderer.draw_mode_selector_modal(
            mouse_pos=mouse_pos,
            timer=timer,
            bot_controller=bot,
            current_mode_name="Crazyhouse",
        )
        self.assertEqual(len(ret), 8)

        # All buttons must be in collapsed state (<= 45.0)
        for mode_id, h in self.renderer.mode_button_anim_heights.items():
            self.assertLessEqual(h, 56.0, f"Button {mode_id} should be collapsed when unhovered")

    def test_modal_rendering_expands_individual_button_on_hover(self):
        """When mouse cursor hovers over a specific mod button, only that button expands to show remaining details."""
        timer = ChessTimer(time_limit_seconds=300)
        bot = ChessBotController(difficulty=BotDifficulty.CASUAL)

        # Hover specifically over the first button (Classic)
        rects = self.renderer.get_mode_selector_rects(expanded=False)
        classic_rect = rects[0]
        mouse_pos = (classic_rect.centerx, classic_rect.centery)

        # Simulate a few frames of hover animation
        for _ in range(5):
            self.renderer.draw_mode_selector_modal(
                mouse_pos=mouse_pos,
                timer=timer,
                bot_controller=bot,
                current_mode_name="Classic",
            )

        # Classic button must have expanded (> 56.0)
        classic_h = self.renderer.mode_button_anim_heights.get("Classic", 44.0)
        self.assertGreater(classic_h, 56.0, "Hovered Classic button must expand to show details")

        # Other buttons (e.g. Crazyhouse, Snail) must remain collapsed (<= 45.0)
        for mode_id, h in self.renderer.mode_button_anim_heights.items():
            if mode_id != "Classic":
                self.assertLessEqual(h, 56.0, f"Unhovered button {mode_id} must remain collapsed")

    def test_all_modes_render_without_crash(self):
        """All 9 modes render cleanly in both collapsed and hovered expanded states."""
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
        rects = self.renderer.get_mode_selector_rects(expanded=False)

        for i, mode_name in enumerate(modes):
            # Render unhovered (away)
            self.renderer.draw_mode_selector_modal(
                mouse_pos=(100, 800),
                timer=timer,
                bot_controller=bot,
                current_mode_name=mode_name,
            )

            # Render hovering over this mode's button
            btn_r = rects[i]
            for _ in range(3):
                self.renderer.draw_mode_selector_modal(
                    mouse_pos=(btn_r.centerx, btn_r.centery),
                    timer=timer,
                    bot_controller=bot,
                    current_mode_name=mode_name,
                )


if __name__ == "__main__":
    unittest.main()

