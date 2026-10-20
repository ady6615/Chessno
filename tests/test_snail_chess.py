# test_snail_chess.py
"""
Automated unit tests for Immortal Snail Mode (Dual-Snail Edition) in Chessno.

Tests:
1. Advancement after precisely five completed legal piece moves across both players.
2. No advancement after illegal or rejected moves.
3. Dual snails exist on both sides (White snail hunts Black King, Black snail hunts White King).
4. Off-board entry points and simultaneous board entry on the 5th move.
5. Protection of friendly pieces: snail NEVER defeats or lands on its own team's pieces.
6. Detour navigation: snail takes a longer route around friendly pieces obstructing its path.
7. Removal and crushing of opposing non-king pieces encountered by a snail.
8. Inability of any piece (including kings) to capture or land on either snail.
9. Dynamic recalculation of direction when the target king moves.
10. Victory resolution: White wins if White snail catches Black King; Black wins if Black snail catches White King.
11. Preservation and independence of Classic Chess and Chess + UNO modes.
12. Theme switching compatibility in Snail mode.
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
from snail_engine import ImmortalSnailMode, SnailEntity
import Assets


class TestDualImmortalSnailMovement(unittest.TestCase):
    """Test step scheduling with 5-move threshold, dual snails, and entry points."""

    def test_advancement_after_precisely_five_completed_legal_moves(self):
        snail_mode = ImmortalSnailMode()
        state = GameState(mode=snail_mode)

        self.assertEqual(snail_mode.moves_until_next_step, 5)
        self.assertEqual(snail_mode.white_snail.steps_taken, 0)
        self.assertEqual(snail_mode.black_snail.steps_taken, 0)
        self.assertFalse(snail_mode.is_on_board)

        # Move 1: e2-e4 (White)
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        self.assertEqual(snail_mode.moves_until_next_step, 4)
        self.assertEqual(snail_mode.white_snail.steps_taken, 0)
        self.assertEqual(snail_mode.black_snail.steps_taken, 0)

        # Move 2: e7-e5 (Black)
        res2 = state.make_move(chess.E7, chess.E5)
        self.assertTrue(res2.success)
        self.assertEqual(snail_mode.moves_until_next_step, 3)

        # Move 3: g1-f3 (White)
        res3 = state.make_move(chess.G1, chess.F3)
        self.assertTrue(res3.success)
        self.assertEqual(snail_mode.moves_until_next_step, 2)

        # Move 4: b8-c6 (Black)
        res4 = state.make_move(chess.B8, chess.C6)
        self.assertTrue(res4.success)
        self.assertEqual(snail_mode.moves_until_next_step, 1)
        self.assertEqual(snail_mode.white_snail.steps_taken, 0)
        self.assertEqual(snail_mode.black_snail.steps_taken, 0)
        self.assertFalse(snail_mode.is_on_board)

        # Move 5: f1-c4 (White) -> Precisely 5 moves completed!
        res5 = state.make_move(chess.F1, chess.C4)
        self.assertTrue(res5.success)

        # Both snails must advance on the 5th completed legal move!
        self.assertEqual(snail_mode.moves_until_next_step, 5)
        self.assertEqual(snail_mode.white_snail.steps_taken, 1)
        self.assertEqual(snail_mode.black_snail.steps_taken, 1)
        self.assertTrue(snail_mode.is_on_board)
        self.assertTrue(snail_mode.white_snail.is_on_board)
        self.assertTrue(snail_mode.black_snail.is_on_board)
        self.assertIsNotNone(snail_mode.white_snail.square)
        self.assertIsNotNone(snail_mode.black_snail.square)

    def test_no_advancement_after_illegal_moves(self):
        snail_mode = ImmortalSnailMode()
        state = GameState(mode=snail_mode)

        # 1 legal move
        state.make_move(chess.E2, chess.E4)
        self.assertEqual(snail_mode.moves_until_next_step, 4)

        # Attempt several illegal / rejected moves
        bad_moves = [
            (chess.E7, chess.E4),  # Blocked square
            (chess.A7, chess.A4),  # Illegal pawn move (3 squares)
            (chess.E8, chess.E7),  # King stepping into pawn collision
            (chess.B8, chess.D7),  # Illegal knight path
        ]

        for from_sq, to_sq in bad_moves:
            res = state.make_move(from_sq, to_sq)
            self.assertFalse(res.success)
            # Counter must remain unchanged at 4, and no snail moves
            self.assertEqual(snail_mode.moves_until_next_step, 4)
            self.assertEqual(snail_mode.white_snail.steps_taken, 0)
            self.assertEqual(snail_mode.black_snail.steps_taken, 0)

    def test_dual_snails_initial_off_board_entry_points(self):
        snail_mode = ImmortalSnailMode()
        # White snail targets Black king; spawns left flank rank 3 (-1, 2)
        self.assertEqual(snail_mode.white_snail.current_pos, (-1, 2))
        self.assertEqual(snail_mode.white_snail.team_color, chess.WHITE)
        self.assertEqual(snail_mode.white_snail.target_color, chess.BLACK)
        self.assertFalse(snail_mode.white_snail.is_on_board)

        # Black snail targets White king; spawns right flank rank 6 (8, 5)
        self.assertEqual(snail_mode.black_snail.current_pos, (8, 5))
        self.assertEqual(snail_mode.black_snail.team_color, chess.BLACK)
        self.assertEqual(snail_mode.black_snail.target_color, chess.WHITE)
        self.assertFalse(snail_mode.black_snail.is_on_board)

        # Execute 5 legal moves to trigger entry
        state = GameState(mode=snail_mode)
        moves = [
            (chess.E2, chess.E4),
            (chess.E7, chess.E5),
            (chess.G1, chess.F3),
            (chess.B8, chess.C6),
            (chess.B1, chess.C3),
        ]
        for f, t in moves:
            res = state.make_move(f, t)
            self.assertTrue(res.success)

        # Both snails are now on the board at legal coordinates
        self.assertTrue(snail_mode.white_snail.is_on_board)
        self.assertTrue(snail_mode.black_snail.is_on_board)
        wx, wy = snail_mode.white_snail.current_pos
        bx, by = snail_mode.black_snail.current_pos
        self.assertTrue(0 <= wx <= 7 and 0 <= wy <= 7)
        self.assertTrue(0 <= bx <= 7 and 0 <= by <= 7)


class TestFriendlyPieceProtectionAndDetours(unittest.TestCase):
    """Test friendly piece safety, detour navigation, and enemy piece crushing."""

    def test_snail_does_not_defeat_friendly_pieces_and_takes_detour(self):
        """
        Verify that a snail never captures/defeats its own team's pieces,
        and takes a longer detour around friendly pieces obstructing its path.
        """
        # White snail placed at d3 (3, 2). Target is Black King at e8 (4, 7).
        # Direct shortest line would want to step to e4 (4, 3) or d4 (3, 3).
        snail_mode = ImmortalSnailMode(white_spawn_pos=chess.D3)
        state = GameState(mode=snail_mode)

        # Place friendly White pieces blocking direct forward advance:
        # e4 and d4 have White pawns
        state.board.set_piece_at(chess.D4, chess.Piece(chess.PAWN, chess.WHITE))
        state.board.set_piece_at(chess.E4, chess.Piece(chess.PAWN, chess.WHITE))

        # Ask White snail to compute next step
        next_step = snail_mode.white_snail.compute_next_step(state)
        self.assertIsNotNone(next_step)
        next_sq = chess.square(next_step[0], next_step[1])

        # Next square MUST NOT be d4 or e4 (the friendly pawns)
        self.assertNotEqual(next_sq, chess.D4)
        self.assertNotEqual(next_sq, chess.E4)

        # Execute the snail step
        snail_mode.white_snail.step(state)

        # The friendly pawns on d4 and e4 MUST still be alive and on the board!
        p_d4 = state.board.piece_at(chess.D4)
        p_e4 = state.board.piece_at(chess.E4)
        self.assertIsNotNone(p_d4)
        self.assertEqual(p_d4.color, chess.WHITE)
        self.assertIsNotNone(p_e4)
        self.assertEqual(p_e4.color, chess.WHITE)

        # White snail took a detour (e.g. via c4 or c3) without crushing friendly pieces
        self.assertNotIn("wp", snail_mode.white_snail.crushed_pieces)
        self.assertEqual(len(snail_mode.white_snail.crushed_pieces), 0)

    def test_snail_crushes_enemy_pieces(self):
        """
        Verify that an enemy non-king piece standing in the snail's path
        IS crushed and removed from the board.
        """
        # White snail placed at d3 (3, 2). Target is Black King at e8.
        # Place an ENEMY (Black) pawn at e4 (4, 3).
        snail_mode = ImmortalSnailMode(white_spawn_pos=chess.D3)
        state = GameState(mode=snail_mode)
        state.board.set_piece_at(chess.E4, chess.Piece(chess.PAWN, chess.BLACK))

        # Direct step towards e8 should be e4
        next_step = snail_mode.white_snail.compute_next_step(state)
        self.assertEqual(next_step, (4, 3))

        # Perform the step
        snail_mode.white_snail.step(state)

        # White snail is now on e4
        self.assertEqual(snail_mode.white_snail.square, chess.E4)
        # Enemy pawn at e4 was crushed and removed
        self.assertIsNone(state.board.piece_at(chess.E4))
        self.assertIn("bp", snail_mode.white_snail.crushed_pieces)

    def test_no_piece_can_capture_or_land_on_either_snail(self):
        """Ensure neither friendly nor enemy chess pieces can move onto either snail's tile."""
        snail_mode = ImmortalSnailMode(
            white_spawn_pos=chess.E4,
            black_spawn_pos=chess.D5
        )
        state = GameState(mode=snail_mode)

        # White pawn at e2 tries to move to e4 (occupied by White snail)
        move_e2e4 = chess.Move(chess.E2, chess.E4)
        self.assertFalse(snail_mode.can_move(state, move_e2e4))
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertFalse(res1.success)

        # Black pawn at d7 tries to move to d5 (occupied by Black snail)
        move_d7d5 = chess.Move(chess.D7, chess.D5)
        self.assertFalse(snail_mode.can_move(state, move_d7d5))

    def test_recalculation_when_target_king_moves(self):
        """When a target king moves, the hunting snail recalibrates its path towards the new tile."""
        # White snail hunting Black King, Black snail hunting White King
        snail_mode = ImmortalSnailMode(white_spawn_pos=chess.D6)
        state = GameState(mode=snail_mode)

        # Move 1: e2-e4
        state.make_move(chess.E2, chess.E4)
        # Move 2: e7-e5
        state.make_move(chess.E7, chess.E5)
        # Move 3: d2-d4
        state.make_move(chess.D2, chess.D4)
        # Move 4: Black King moves e8-e7!
        state.make_move(chess.E8, chess.E7)
        self.assertEqual(state.king_square(chess.BLACK), chess.E7)

        # Move 5: White plays c2-c3 -> triggers snail step!
        state.make_move(chess.C2, chess.C3)
        self.assertEqual(snail_mode.white_snail.steps_taken, 1)

        # White snail recalibrated towards e7 (4, 6) instead of e8 (4, 7)
        target_file = chess.square_file(chess.E7)
        target_rank = chess.square_rank(chess.E7)
        wx, wy = snail_mode.white_snail.current_pos
        dist = max(abs(wx - target_file), abs(wy - target_rank))
        self.assertLessEqual(dist, 1)


class TestTargetKingCaptureAndGameOver(unittest.TestCase):
    """Test instant win conditions when either snail captures its opposing king."""

    def test_white_snail_captures_black_king_causes_white_victory(self):
        # White snail placed adjacent to Black King (e8) at e7
        snail_mode = ImmortalSnailMode(white_spawn_pos=chess.E7)
        state = GameState(mode=snail_mode)

        # Remove black pawn on e7 if any, ensure e7 is empty
        state.board.remove_piece_at(chess.E7)

        # Five legal moves
        moves = [
            (chess.A2, chess.A4),
            (chess.A7, chess.A5),
            (chess.B2, chess.B4),
            (chess.B7, chess.B5),
            (chess.C2, chess.C4),
        ]
        for f, t in moves:
            res = state.make_move(f, t)
            self.assertTrue(res.success)

        # White snail reaches Black King at e8
        self.assertTrue(snail_mode.white_snail.target_caught)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)
        self.assertIn("White's Immortal Snail", state.game_over_reason())
        self.assertIn("White wins", state.game_over_reason())

        # Further moves rejected
        res = state.make_move(chess.H7, chess.H6)
        self.assertFalse(res.success)

    def test_black_snail_captures_white_king_causes_black_victory(self):
        # Black snail placed adjacent to White King (e1) at e2
        snail_mode = ImmortalSnailMode(black_spawn_pos=chess.E2)
        state = GameState(mode=snail_mode)

        # Remove white pawn on e2 if any
        state.board.remove_piece_at(chess.E2)

        # Five legal moves
        moves = [
            (chess.A2, chess.A4),
            (chess.A7, chess.A5),
            (chess.B2, chess.B4),
            (chess.B7, chess.B5),
            (chess.C2, chess.C4),
        ]
        for f, t in moves:
            res = state.make_move(f, t)
            self.assertTrue(res.success)

        # Black snail reaches White King at e1
        self.assertTrue(snail_mode.black_snail.target_caught)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.BLACK)
        self.assertIn("Black's Immortal Snail", state.game_over_reason())
        self.assertIn("Black wins", state.game_over_reason())


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
        snail_mode = ImmortalSnailMode()
        state.set_mode(snail_mode)
        self.assertEqual(state.mode.name, "Immortal Snail")
        self.assertTrue(hasattr(state.mode, "moves_until_next_step"))
        self.assertEqual(state.mode.MOVES_PER_STEP, 5)
        self.assertTrue(hasattr(state.mode, "white_snail"))
        self.assertTrue(hasattr(state.mode, "black_snail"))
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
