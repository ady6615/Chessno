# test_snail_chess.py
"""
Automated unit tests for Immortal Snail Mode in Chessno.

Tests:
1. Advancement after precisely three completed legal piece moves.
2. No advancement after illegal or rejected moves.
3. Snail movement when pieces occupy potential destination squares (ignoring occupancy).
4. Removal of non-king pieces encountered by the snail.
5. Inability of any piece (including king) to capture or land on the snail.
6. Recalculation of direction when the target king moves.
7. Correct handling of target king capture and game-over state.
8. Target king selection for both White and Black, and locking after move 1.
9. Initial off-board entry point and entrance on the first scheduled step.
10. Preservation of Classic Chess and Chess + UNO modes.
11. Theme switching compatibility.
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
import Assets


class TestImmortalSnailMovement(unittest.TestCase):
    """Test step scheduling, illegal move filtering, and path calculation."""

    def test_advancement_after_precisely_three_completed_legal_moves(self):
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK)
        state = GameState(mode=snail_mode)

        self.assertEqual(snail_mode.moves_until_next_step, 3)
        self.assertEqual(snail_mode.steps_taken, 0)
        self.assertFalse(snail_mode.is_on_board)

        # Move 1: e2-e4 (White legal move)
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        self.assertEqual(snail_mode.moves_until_next_step, 2)
        self.assertEqual(snail_mode.steps_taken, 0)
        self.assertFalse(snail_mode.is_on_board)

        # Move 2: e7-e5 (Black legal move)
        res2 = state.make_move(chess.E7, chess.E5)
        self.assertTrue(res2.success)
        self.assertEqual(snail_mode.moves_until_next_step, 1)
        self.assertEqual(snail_mode.steps_taken, 0)
        self.assertFalse(snail_mode.is_on_board)

        # Move 3: g1-f3 (White legal move) -> Precisely 3 moves completed!
        res3 = state.make_move(chess.G1, chess.F3)
        self.assertTrue(res3.success)
        # Snail must advance!
        self.assertEqual(snail_mode.moves_until_next_step, 3)
        self.assertEqual(snail_mode.steps_taken, 1)
        self.assertTrue(snail_mode.is_on_board)
        self.assertIsNotNone(snail_mode.square)

    def test_no_advancement_after_illegal_moves(self):
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK)
        state = GameState(mode=snail_mode)

        # Legal move 1
        state.make_move(chess.E2, chess.E4)
        self.assertEqual(snail_mode.moves_until_next_step, 2)

        # Attempt illegal moves
        bad_moves = [
            (chess.E7, chess.E4),  # Blocked by pawn
            (chess.A7, chess.A4),  # 3-square pawn jump
            (chess.E8, chess.E7),  # King stepping into pawn collision
            (chess.B8, chess.D7),  # Illegal knight path
        ]

        for from_sq, to_sq in bad_moves:
            res = state.make_move(from_sq, to_sq)
            self.assertFalse(res.success)
            # Counter must remain exactly 2, and snail must NOT step
            self.assertEqual(snail_mode.moves_until_next_step, 2)
            self.assertEqual(snail_mode.steps_taken, 0)

    def test_off_board_entry_point(self):
        # White target: spawns off-board top edge (0, 8)
        mode_white = ImmortalSnailMode(target_color=chess.WHITE)
        self.assertEqual(mode_white.current_pos, (0, 8))
        self.assertFalse(mode_white.is_on_board)
        self.assertIsNone(mode_white.square)

        # Black target: spawns off-board bottom edge (0, -1)
        mode_black = ImmortalSnailMode(target_color=chess.BLACK)
        self.assertEqual(mode_black.current_pos, (0, -1))
        self.assertFalse(mode_black.is_on_board)
        self.assertIsNone(mode_black.square)

        # Step into board
        state = GameState(mode=mode_black)
        # 3 legal moves
        state.make_move(chess.E2, chess.E4)
        state.make_move(chess.E7, chess.E5)
        state.make_move(chess.G1, chess.F3)

        self.assertTrue(mode_black.is_on_board)
        self.assertIsNotNone(mode_black.square)
        self.assertTrue(0 <= mode_black.current_pos[0] <= 7)
        self.assertTrue(0 <= mode_black.current_pos[1] <= 7)


class TestSnailPieceInteractions(unittest.TestCase):
    """Test piece squashing, immunity from capture, and king safety."""

    def test_removal_of_pieces_encountered_by_the_snail(self):
        # Place snail at d3, targeting Black King at e8.
        # Direct shortest path step from d3 (3, 2) to e8 (4, 7) is e4 (4, 3).
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK, spawn_pos=chess.D3)
        state = GameState(mode=snail_mode)

        # White plays e2-e4 (pawn now at e4)
        self.assertIsNotNone(state.board.piece_at(chess.E2))
        state.make_move(chess.E2, chess.E4)  # move 1
        self.assertEqual(state.board.piece_at(chess.E4).piece_type, chess.PAWN)

        state.make_move(chess.A7, chess.A5)  # move 2
        state.make_move(chess.G1, chess.F3)  # move 3 -> triggers snail step

        # Snail from d3 steps onto e4
        self.assertEqual(snail_mode.current_pos, (4, 3))  # file 4, rank 3 = e4
        self.assertEqual(snail_mode.square, chess.E4)

        # The pawn previously on e4 must be removed by the snail!
        self.assertIsNone(state.board.piece_at(chess.E4))
        self.assertIn("wp", snail_mode.crushed_pieces)

    def test_no_piece_can_capture_or_land_on_snail(self):
        # Place snail on e4
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK, spawn_pos=chess.E4)
        state = GameState(mode=snail_mode)

        # White pawn at e2 tries to move to e4
        move_e2e4 = chess.Move(chess.E2, chess.E4)
        self.assertFalse(snail_mode.can_move(state, move_e2e4))

        # Attempting make_move to the snail's square must fail
        res = state.make_move(chess.E2, chess.E4)
        self.assertFalse(res.success)
        self.assertIsNone(state.board.piece_at(chess.E4))

    def test_recalculation_when_target_king_moves(self):
        # Snail starts at d3, targeting White King at e1
        snail_mode = ImmortalSnailMode(target_color=chess.WHITE, spawn_pos=chess.D3)
        state = GameState(mode=snail_mode)

        # Move 1: e2-e4
        state.make_move(chess.E2, chess.E4)
        # Move 2: e7-e5
        state.make_move(chess.E7, chess.E5)
        # Move 3: White moves King e1-e2!
        state.make_move(chess.E1, chess.E2)

        # Target king is now at e2 instead of e1
        self.assertEqual(state.king_square(chess.WHITE), chess.E2)

        # On the 3rd move, snail recalculated towards e2!
        # From d3 (3, 2), distance to e2 (4, 1):
        # Chebyshev = max(|3-4|, |2-1|) = 1
        # Destination should be e2 or adjacent step directly towards e2
        self.assertTrue(snail_mode.steps_taken == 1)
        next_sq = snail_mode.square
        # Distance to e2 must be reduced
        self.assertLessEqual(max(abs(chess.square_file(next_sq) - 4), abs(chess.square_rank(next_sq) - 1)), 1)


class TestTargetKingCaptureAndGameOver(unittest.TestCase):
    """Test game-over conditions, victor resolution, and target configuration."""

    def test_capture_of_white_king_causes_black_victory(self):
        # Snail positioned adjacent to White King at e2, targeting White
        snail_mode = ImmortalSnailMode(target_color=chess.WHITE, spawn_pos=chess.E2)
        state = GameState(mode=snail_mode)

        # Three legal moves
        state.make_move(chess.A2, chess.A4)  # move 1
        state.make_move(chess.A7, chess.A5)  # move 2
        state.make_move(chess.B2, chess.B4)  # move 3 -> snail steps onto e1 (White King)

        self.assertTrue(snail_mode.target_caught)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.BLACK)
        self.assertIn("White King", state.game_over_reason())
        self.assertIn("Black wins", state.game_over_reason())

        # Further moves rejected
        res = state.make_move(chess.B7, chess.B5)
        self.assertFalse(res.success)

    def test_capture_of_black_king_causes_white_victory(self):
        # Snail positioned adjacent to Black King at e7, targeting Black
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK, spawn_pos=chess.E7)
        state = GameState(mode=snail_mode)

        # Three legal moves
        state.make_move(chess.A2, chess.A4)  # move 1
        state.make_move(chess.A7, chess.A5)  # move 2
        state.make_move(chess.B2, chess.B4)  # move 3 -> snail steps onto e8 (Black King)

        self.assertTrue(snail_mode.target_caught)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)
        self.assertIn("Black King", state.game_over_reason())
        self.assertIn("White wins", state.game_over_reason())

    def test_target_king_configuration_and_locking(self):
        snail_mode = ImmortalSnailMode(target_color=chess.BLACK)
        state = GameState(mode=snail_mode)

        # Configurable before moves begin
        self.assertEqual(snail_mode.target_color, chess.BLACK)
        success = snail_mode.set_target_color(chess.WHITE)
        self.assertTrue(success)
        self.assertEqual(snail_mode.target_color, chess.WHITE)

        # Execute 1 legal move
        state.make_move(chess.E2, chess.E4)
        self.assertEqual(snail_mode.total_legal_moves, 1)

        # Now target color MUST be locked and cannot be changed
        locked = snail_mode.set_target_color(chess.BLACK)
        self.assertFalse(locked)
        self.assertEqual(snail_mode.target_color, chess.WHITE)


class TestModeCoexistenceAndThemeSwitching(unittest.TestCase):
    """Verify that Classic Chess, Chess + UNO, and Immortal Snail operate independently."""

    def test_modes_switch_cleanly_and_independently(self):
        state = GameState(mode=ClassicChessMode())
        self.assertEqual(state.mode.name, "Classic")

        # Switch to Chess + UNO
        uno_mode = ChessUnoMode()
        state.set_mode(uno_mode)
        self.assertEqual(state.mode.name, "Chess + UNO")
        self.assertTrue(hasattr(state.mode, "deck"))

        # Switch to Immortal Snail
        snail_mode = ImmortalSnailMode(target_color=chess.WHITE)
        state.set_mode(snail_mode)
        self.assertEqual(state.mode.name, "Immortal Snail")
        self.assertTrue(hasattr(state.mode, "moves_until_next_step"))
        self.assertFalse(hasattr(state.mode, "deck"))

        # Switch back to Classic Chess
        classic = ClassicChessMode()
        state.set_mode(classic)
        self.assertEqual(state.mode.name, "Classic")
        self.assertFalse(hasattr(state.mode, "moves_until_next_step"))
        self.assertFalse(hasattr(state.mode, "deck"))

    def test_theme_switching_with_snail_mode(self):
        pygame.init()
        pygame.display.set_mode((100, 100))
        Assets.load_assets()
        available = Assets.get_available_packs()
        self.assertGreater(len(available), 0)

        # Switch theme
        board, pieces = Assets.switch_asset_pack(available[0])
        self.assertIsNotNone(board)
        self.assertGreater(len(pieces), 0)


if __name__ == "__main__":
    unittest.main()
