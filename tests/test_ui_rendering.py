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

    def test_rook_dash_mode_panel_rendering(self):
        from rook_dash_engine import RookDashMode
        state = GameState(mode=RookDashMode())
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

    def test_bishop_dash_mode_panel_rendering(self):
        from bishop_dash_engine import BishopDashMode
        state = GameState(mode=BishopDashMode())
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
        self.assertEqual(len(rects), 7)

    def test_winning_popup_rendering_white_wins(self):
        state = GameState()
        # White wins by timeout
        state.set_timeout(chess.BLACK)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)

        popup_rect = self.renderer.get_game_over_popup_rect()
        # Center should be in the middle of the board (50 + 400, 50 + 400) = (450, 450)
        self.assertEqual(popup_rect.center, (450, 450))

        restart_btn = self.renderer.draw_game_over_popup(state, mouse_pos=(450, 450))
        self.assertTrue(popup_rect.contains(restart_btn))

    def test_winning_popup_rendering_black_wins(self):
        state = GameState()
        # Black wins by timeout
        state.set_timeout(chess.WHITE)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.BLACK)

        restart_btn = self.renderer.draw_game_over_popup(state, mouse_pos=(0, 0))
        self.assertIsNotNone(restart_btn)

    def test_winning_popup_rendering_tie(self):
        state = GameState(mode=QueenPawnMode())
        # Board with only queens (Tie)
        state.board = chess.Board("3q4/8/8/8/8/8/8/3Q4 w - - 0 1")
        self.assertTrue(state.is_game_over())
        self.assertIsNone(state.winner())

        restart_btn = self.renderer.draw_game_over_popup(state, mouse_pos=(0, 0))
        self.assertIsNotNone(restart_btn)

    def test_fullscreen_button_presence_and_bounds(self):
        """Verify that the Fullscreen toggle button exists and is positioned in the panel header."""
        self.assertTrue(hasattr(self.renderer.buttons, "fullscreen"))
        fs_rect = self.renderer.buttons.fullscreen
        self.assertGreaterEqual(fs_rect.x, self.renderer.panel_x)
        self.assertLessEqual(fs_rect.right, self.renderer.panel_x + self.renderer.panel_width)

    def test_fullscreen_panel_rendering(self):
        """Verify that panel renders cleanly both in windowed and fullscreen modes."""
        state = GameState(mode=ClassicChessMode())
        # Windowed mode
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
            is_fullscreen=False,
        )
        # Fullscreen mode
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
            is_fullscreen=True,
        )

    def test_board_rendering_coordinates(self):
        """Verify board rendering with algebraic coordinates in standard and flipped views."""
        # Standard White view
        self.renderer.draw_board(self.board_img, flipped=False)
        # Flipped Black view
        self.renderer.draw_board(self.board_img, flipped=True)

    def test_bot_ui_buttons_and_modal_rects(self):
        """Verify bot buttons exist on UIButtons and modal rects function properly."""
        from ai_bot import ChessBotController, BotDifficulty
        self.assertTrue(hasattr(self.renderer.buttons, "bot_toggle"))
        self.assertTrue(hasattr(self.renderer.buttons, "bot_difficulty"))
        self.assertTrue(hasattr(self.renderer.buttons, "bot_quick_toggle"))

        # Check AI modal rects
        vs_bot, vs_local, diffs, sides, start_btn = self.renderer.get_mode_selector_ai_rects()
        self.assertIsNotNone(vs_bot)
        self.assertIsNotNone(vs_local)
        self.assertEqual(len(diffs), 4)
        self.assertEqual(len(sides), 3)
        self.assertIsNotNone(start_btn)

    def test_bot_panel_and_modal_rendering(self):
        """Verify panel and modal render cleanly with bot controller."""
        from ai_bot import ChessBotController, BotDifficulty
        bot_ctrl = ChessBotController(difficulty=BotDifficulty.INTERMEDIATE)
        state = GameState(mode=ClassicChessMode())

        # Test panel with bot controller
        self.renderer.draw_panel(
            game_state=state,
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            mouse_pos=(950, 500),
            sound_enabled=True,
            flipped=False,
            piece_images=self.piece_images,
            bot_controller=bot_ctrl,
        )

        # Test modal with bot controller
        mode_rects = self.renderer.draw_mode_selector_modal(
            mouse_pos=(600, 400),
            bot_controller=bot_ctrl,
        )
        self.assertEqual(len(mode_rects), 7)

    def test_hero_mode_panel_rendering(self):
        from hero_mode_engine import HeroMode
        state = GameState(mode=HeroMode())
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

    def test_game_start_bounce_animation_lifecycle(self):
        """Verify lifecycle of GameStartBounceAnimation (inactive, trigger, update, complete, cancel)."""
        from renderer import GameStartBounceAnimation
        anim = GameStartBounceAnimation(piece_duration=0.5, max_height=40.0)
        self.assertFalse(anim.is_active)

        # Trigger
        anim.trigger()
        self.assertTrue(anim.is_active)
        self.assertEqual(anim.elapsed, 0.0)

        # Update partially
        anim.update(0.2)
        self.assertTrue(anim.is_active)
        self.assertAlmostEqual(anim.elapsed, 0.2)

        # Cancel
        anim.cancel()
        self.assertFalse(anim.is_active)
        self.assertEqual(anim.elapsed, 0.0)

        # Re-trigger and advance to completion
        anim.trigger()
        anim.update(anim.total_duration + 0.1)
        self.assertFalse(anim.is_active)

    def test_bounce_offset_and_stagger_calculations(self):
        """Verify vertical offset trajectory, gravity parabola, and staggered timing across columns and pieces."""
        from renderer import GameStartBounceAnimation
        anim = GameStartBounceAnimation(piece_duration=0.5, max_height=40.0, stagger_col=0.03, stagger_pawn=0.05)

        # When inactive, offset is 0 and shadow scale is 1.0
        y_off, shadow_scale = anim.get_offset(col=0, is_pawn=False)
        self.assertEqual(y_off, 0.0)
        self.assertEqual(shadow_scale, 1.0)

        anim.trigger()
        # At t=0.15s: col 0 is actively in mid-air
        anim.update(0.15)
        y_col0, s_col0 = anim.get_offset(col=0, is_pawn=False)
        self.assertLess(y_col0, -5.0)  # Ascended upward
        self.assertLessEqual(s_col0, 1.0)
        self.assertGreaterEqual(s_col0, 0.4)

        # col 7 has delay = 7 * 0.03 = 0.21s; at elapsed=0.15s, local t < 0, so still grounded
        y_col7, s_col7 = anim.get_offset(col=7, is_pawn=False)
        self.assertEqual(y_col7, 0.0)
        self.assertEqual(s_col7, 1.0)

    def test_renderer_bounce_integration_and_drawing(self):
        """Verify ChessRenderer bounce triggering, updating, and drawing pieces with bounce and shadows."""
        state = GameState(mode=ClassicChessMode())
        self.renderer.cancel_start_bounce()
        self.assertFalse(self.renderer.is_bounce_animating())

        # Trigger on renderer
        self.renderer.trigger_start_bounce()
        self.assertTrue(self.renderer.is_bounce_animating())

        # Advance into mid-bounce
        self.renderer.update_start_bounce(0.25)
        self.assertTrue(self.renderer.is_bounce_animating())

        # draw_pieces with bounce active should execute cleanly without error
        self.renderer.draw_pieces(
            game_state=state,
            piece_images=self.piece_images,
            flipped=False,
            apply_bounce=True,
        )

        # draw_pieces with flipped=True
        self.renderer.draw_pieces(
            game_state=state,
            piece_images=self.piece_images,
            flipped=True,
            apply_bounce=True,
        )

        # Cancel bounce
        self.renderer.cancel_start_bounce()
        self.assertFalse(self.renderer.is_bounce_animating())

        # Drawing with bounce inactive renders standard resting pieces
        self.renderer.draw_pieces(
            game_state=state,
            piece_images=self.piece_images,
            flipped=False,
            apply_bounce=True,
        )

    def test_piece_reset_return_animation_lifecycle(self):
        """Verify lifecycle of PieceResetReturnAnimation (trigger, update, finish, cancel)."""
        from renderer import PieceResetReturnAnimation
        from coordinates import BOARD_X, BOARD_Y, SQUARE_SIZE

        anim = PieceResetReturnAnimation(duration=0.5)
        self.assertFalse(anim.is_active)

        state = GameState(mode=ClassicChessMode())
        # Make a move so pieces have displaced positions
        state.make_move(chess.E2, chess.E4)
        end_pieces = {sq: state.get_piece_at(sq) for sq in chess.SQUARES if state.get_piece_at(sq) is not None}
        state.reset()
        target_pieces = {sq: state.get_piece_at(sq) for sq in chess.SQUARES if state.get_piece_at(sq) is not None}

        piece_sizes = {code: (img.get_width(), img.get_height()) for code, img in self.piece_images.items()}
        started = anim.trigger(
            end_pieces=end_pieces,
            target_pieces=target_pieces,
            flipped=False,
            board_x=BOARD_X,
            board_y=BOARD_Y,
            square_size=SQUARE_SIZE,
            caps_origin=(990, 620),
            piece_sizes=piece_sizes,
        )
        self.assertTrue(started)
        self.assertTrue(anim.is_active)
        self.assertEqual(len(anim.tracks), 32)

        # Update partially
        finished = anim.update(0.25)
        self.assertFalse(finished)
        self.assertTrue(anim.is_active)
        self.assertAlmostEqual(anim.progress, 0.5)

        # Cancel
        anim.cancel()
        self.assertFalse(anim.is_active)
        self.assertEqual(len(anim.tracks), 0)

        # Retrigger and advance to completion
        anim.trigger(
            end_pieces=end_pieces,
            target_pieces=target_pieces,
            flipped=False,
            board_x=BOARD_X,
            board_y=BOARD_Y,
            square_size=SQUARE_SIZE,
            caps_origin=(990, 620),
            piece_sizes=piece_sizes,
        )
        finished = anim.update(0.6)
        self.assertTrue(finished)
        self.assertFalse(anim.is_active)

    def test_piece_reset_return_renderer_integration(self):
        """Verify ChessRenderer reset return animation triggering, updating, chaining bounce, and drawing."""
        state = GameState(mode=ClassicChessMode())
        # Make moves including a capture
        state.make_move(chess.E2, chess.E4)
        state.make_move(chess.D7, chess.D5)
        state.make_move(chess.E4, chess.D5)

        end_pieces = {sq: state.get_piece_at(sq) for sq in chess.SQUARES if state.get_piece_at(sq) is not None}
        state.reset()

        # Trigger reset return on renderer
        started = self.renderer.trigger_reset_return(
            end_pieces=end_pieces,
            game_state=state,
            piece_images=self.piece_images,
            flipped=False,
        )
        self.assertTrue(started)
        self.assertTrue(self.renderer.is_return_animating())
        self.assertFalse(self.renderer.is_bounce_animating())

        # Render frame during return animation
        self.renderer.draw_pieces(
            game_state=state,
            piece_images=self.piece_images,
            flipped=False,
        )

        # Render frame with flipped=True
        self.renderer.draw_pieces(
            game_state=state,
            piece_images=self.piece_images,
            flipped=True,
        )

        # Advance until return animation finishes
        finished = self.renderer.update_reset_return(0.7)
        self.assertTrue(finished)
        self.assertFalse(self.renderer.is_return_animating())
        # Should have automatically chained into the start bounce animation!
        self.assertTrue(self.renderer.is_bounce_animating())

        # Clean up
        self.renderer.cancel_start_bounce()
        self.assertFalse(self.renderer.is_bounce_animating())

    def test_fullscreen_layout_adaptation(self):
        """Verify dynamic layout updates across standard, 1080p, 1440p, 4K, and ultrawide fullscreen resolutions."""
        resolutions = [
            (1200, 900, False),    # Default windowed
            (1920, 1080, True),    # Standard 1080p 16:9 Fullscreen
            (1920, 1200, True),    # 16:10 Fullscreen
            (2560, 1440, True),    # 1440p 2K Fullscreen
            (3840, 2160, True),    # 4K UHD Fullscreen
            (2560, 1080, True),    # 21:9 Ultrawide Fullscreen
            (1366, 768, True),     # Laptop 768p Fullscreen
        ]

        state = GameState(mode=ClassicChessMode())

        for width, height, is_fs in resolutions:
            surf = pygame.Surface((width, height))
            self.renderer.screen = surf
            self.renderer.update_layout(width, height, is_fullscreen=is_fs)

            # Board must fit within screen bounds
            board_w = 8 * self.renderer.square_size
            board_h = 8 * self.renderer.square_size
            self.assertGreater(self.renderer.square_size, 0)
            self.assertGreaterEqual(self.renderer.board_x, 0)
            self.assertGreaterEqual(self.renderer.board_y, 0)
            self.assertLessEqual(self.renderer.board_x + board_w, self.renderer.panel_x)
            self.assertLessEqual(self.renderer.board_y + board_h, height)

            # Panel must fit on right side
            self.assertLessEqual(self.renderer.panel_x + self.renderer.panel_width, width)

            # Check that drawing routines execute cleanly without error on scaled surfaces
            self.renderer.draw_board(self.board_img)
            self.renderer.draw_pieces(state, self.piece_images)
            self.renderer.draw_panel(
                game_state=state,
                active_pack_name="Default",
                active_pack_index=0,
                total_packs=1,
                mouse_pos=(self.renderer.panel_x + 10, 100),
                sound_enabled=True,
                flipped=False,
                piece_images=self.piece_images,
                is_fullscreen=is_fs,
            )
            self.renderer.draw_mode_selector_modal(mouse_pos=(width // 2, height // 2))

        # Reset back to default 1200x900
        self.renderer.update_layout(1200, 900, is_fullscreen=False)
        self.assertEqual(self.renderer.board_x, 50)
        self.assertEqual(self.renderer.board_y, 50)
        self.assertEqual(self.renderer.square_size, 100)
        self.assertEqual(self.renderer.panel_x, 900)
        self.assertEqual(self.renderer.panel_width, 270)


if __name__ == "__main__":
    unittest.main()

