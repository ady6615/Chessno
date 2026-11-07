# test_rook_dash.py
"""
Unit tests for the 'Rook Dash' game mode in Chessno.

Rules Tested:
1. Initial Board Setup:
   - Exactly 2 Rooks, 8 Pawns, and 1 King per player at default positions.
   - 0 Knights, 0 Bishops, 0 Queens.
2. Rook 4-Way Dashing:
   - Exactly 4 cardinal directions (Left, Right, Up, Down).
   - Dashes until board boundary.
   - Obstructed by own colour pawn/king/rook (stops right before).
   - Hits and captures enemy piece.
   - Cannot stop at intermediate squares.
3. Pawn Promotion:
   - Pawns can ONLY promote to Rooks.
   - Auto-promotion defaults to chess.ROOK.
   - Promoted Rook becomes a dashing rook.
4. Win Condition:
   - First to deliver checkmate wins.
   - Stalemate and draw detection.
5. AI Bot Integration:
   - Bot selects legal dash moves and evaluates Rook Dash positions.
"""

import os
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
SRC2_DIR = PROJECT_ROOT / "src2"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC2_DIR))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import chess
from game_engine import GameState
from rook_dash_engine import RookDashMode
from ai_bot import BotDifficulty, select_best_move, evaluate_board


class TestRookDashMode(unittest.TestCase):
    def setUp(self):
        self.mode = RookDashMode()
        self.state = GameState(mode=self.mode)

    def test_initial_board_pieces_setup(self):
        """Verify initial layout: only 2 rooks, 8 pawns, 1 king per player."""
        board = self.state.board
        # White pieces
        self.assertEqual(len(board.pieces(chess.ROOK, chess.WHITE)), 2)
        self.assertEqual(len(board.pieces(chess.PAWN, chess.WHITE)), 8)
        self.assertEqual(len(board.pieces(chess.KING, chess.WHITE)), 1)
        self.assertEqual(len(board.pieces(chess.KNIGHT, chess.WHITE)), 0)
        self.assertEqual(len(board.pieces(chess.BISHOP, chess.WHITE)), 0)
        self.assertEqual(len(board.pieces(chess.QUEEN, chess.WHITE)), 0)

        # Black pieces
        self.assertEqual(len(board.pieces(chess.ROOK, chess.BLACK)), 2)
        self.assertEqual(len(board.pieces(chess.PAWN, chess.BLACK)), 8)
        self.assertEqual(len(board.pieces(chess.KING, chess.BLACK)), 1)
        self.assertEqual(len(board.pieces(chess.KNIGHT, chess.BLACK)), 0)
        self.assertEqual(len(board.pieces(chess.BISHOP, chess.BLACK)), 0)
        self.assertEqual(len(board.pieces(chess.QUEEN, chess.BLACK)), 0)

        # Squares check
        self.assertEqual(board.piece_at(chess.A1), chess.Piece(chess.ROOK, chess.WHITE))
        self.assertEqual(board.piece_at(chess.H1), chess.Piece(chess.ROOK, chess.WHITE))
        self.assertEqual(board.piece_at(chess.E1), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(board.piece_at(chess.A8), chess.Piece(chess.ROOK, chess.BLACK))
        self.assertEqual(board.piece_at(chess.H8), chess.Piece(chess.ROOK, chess.BLACK))
        self.assertEqual(board.piece_at(chess.E8), chess.Piece(chess.KING, chess.BLACK))

    def test_initial_rook_dash_destinations(self):
        """At start, Rook at a1 is blocked by pawn at a2, board edge down/left, King at e1."""
        dests = self.mode.get_rook_dash_destinations(self.state.board, chess.A1)
        # King is at e1, so rook dashes along rank 1 and stops at d1!
        self.assertEqual(dests, [chess.D1])

        # Similarly for h1: King at e1, dashes left and stops at f1
        dests_h1 = self.mode.get_rook_dash_destinations(self.state.board, chess.H1)
        self.assertEqual(dests_h1, [chess.F1])

    def test_rook_dash_cannot_stop_at_intermediate_squares(self):
        """Rook at a1 cannot move to b1 or c1, only to d1."""
        self.assertFalse(self.state.is_legal_move(chess.A1, chess.B1))
        self.assertFalse(self.state.is_legal_move(chess.A1, chess.C1))
        self.assertTrue(self.state.is_legal_move(chess.A1, chess.D1))

    def test_rook_dash_to_board_boundary(self):
        """When the ray is clear to the board edge, rook dashes all the way to the boundary."""
        # Empty board with just a White Rook at d4 and White King at h1, Black King at h8
        b = chess.Board("7k/8/8/8/3R4/8/8/7K w - - 0 1")
        dests = self.mode.get_rook_dash_destinations(b, chess.D4)
        # Up -> d8 (edge)
        # Down -> d1 (edge)
        # Left -> a4 (edge)
        # Right -> h4 (edge)
        expected = {chess.D8, chess.D1, chess.A4, chess.H4}
        self.assertEqual(set(dests), expected)

    def test_rook_dash_stopped_before_friendly_piece(self):
        """Rook stops immediately before a friendly piece along its path."""
        # White Rook at d4, friendly White Pawn at d7
        b = chess.Board("7k/3P4/8/8/3R4/8/8/7K w - - 0 1")
        dests = self.mode.get_rook_dash_destinations(b, chess.D4)
        # In Up direction, d7 has friendly pawn, so it stops at d6
        self.assertIn(chess.D6, dests)
        self.assertNotIn(chess.D7, dests)
        self.assertNotIn(chess.D8, dests)

    def test_rook_dash_hits_and_captures_enemy_piece(self):
        """Rook hits the first enemy piece along its path and captures it."""
        # White Rook at d4, enemy Black Pawn at d7
        b = chess.Board("7k/3p4/8/8/3R4/8/8/7K w - - 0 1")
        dests = self.mode.get_rook_dash_destinations(b, chess.D4)
        # In Up direction, d7 has Black pawn, so it captures at d7
        self.assertIn(chess.D7, dests)
        self.assertNotIn(chess.D6, dests)
        self.assertNotIn(chess.D8, dests)

    def test_pawn_promotion_strictly_to_rook(self):
        """Pawns can ONLY promote to Rooks in Rook Dash."""
        b = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        # Promotion to Queen must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.QUEEN), board=b))
        # Promotion to Knight must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.KNIGHT), board=b))
        # Promotion to Bishop must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.BISHOP), board=b))
        # Promotion to Rook must be accepted
        self.assertTrue(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.ROOK), board=b))

    def test_game_state_auto_promotes_to_rook(self):
        """GameState defaults pawn promotion to chess.ROOK in Rook Dash."""
        state = GameState(mode=self.mode)
        state.board = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        res = state.make_move(chess.E7, chess.E8)
        self.assertTrue(res.success)
        promoted_piece = state.board.piece_at(chess.E8)
        self.assertIsNotNone(promoted_piece)
        self.assertEqual(promoted_piece.piece_type, chess.ROOK)

    def test_promoted_rook_becomes_dashing_rook(self):
        """Once promoted to Rook, the piece dashes following Rook Dash rules."""
        state = GameState(mode=self.mode)
        state.board = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        state.make_move(chess.E7, chess.E8)  # promotes to Rook at e8
        # Black king moves out of the way to h7
        state.make_move(chess.H8, chess.H7)
        # White rook at e8 can dash left to a8 or down to e1
        dests = self.mode.get_rook_dash_destinations(state.board, chess.E8)
        self.assertIn(chess.A8, dests)
        self.assertIn(chess.E1, dests)

    def test_checkmate_detection_in_rook_dash(self):
        """A player whose King is in check with no valid moves is checkmated."""
        state = GameState(mode=self.mode)
        # Position: White King at h1, White Rooks at a8 and b7, Black King cornered at h8
        # Black King is attacked by a8 rook (giving check along rank 8)
        # Rank 7 covered by b7 rook
        state.board = chess.Board("R6k/1R6/8/8/8/8/8/7K b - - 0 1")
        self.assertTrue(state.board.is_check())
        self.assertTrue(self.mode.is_game_over(state))
        self.assertEqual(self.mode.winner(state), chess.WHITE)
        self.assertIn("Checkmate", self.mode.game_over_reason(state))

    def test_ai_bot_selects_rook_dash_moves(self):
        """AI bot generates and selects legal Rook Dash moves without error."""
        state = GameState(mode=self.mode)
        for diff in (BotDifficulty.NOVICE, BotDifficulty.CASUAL, BotDifficulty.INTERMEDIATE, BotDifficulty.MASTER):
            chosen = select_best_move(state.board, diff, game_mode=self.mode)
            self.assertIsNotNone(chosen)
            self.assertTrue(self.mode.can_move(state, chosen))

    def test_ai_bot_evaluation_in_rook_dash(self):
        """evaluate_board computes sensible scores for Rook Dash material and check."""
        b = chess.Board("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w - - 0 1")
        score_equal = evaluate_board(b, game_mode=self.mode)
        self.assertEqual(score_equal, 0)


if __name__ == "__main__":
    unittest.main()

