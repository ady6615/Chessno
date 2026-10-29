# test_queen_pawn.py
"""Unit tests for the Queen Pawn Game mode in Chessno."""

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

import chess
from game_engine import GameState
from queen_pawn_engine import QueenPawnMode


class TestQueenPawnGame(unittest.TestCase):
    def setUp(self):
        self.mode = QueenPawnMode()
        self.game = GameState(mode=self.mode)

    def test_initial_board_setup(self):
        """Verify the exact board layout specified in the prompt."""
        self.assertEqual(self.game.to_fen(), "3q4/8/8/pppppppp/PPPPPPPP/8/8/3Q4 w - - 0 1")

        # White Queen on d1, Black Queen on d8
        self.assertEqual(self.game.get_piece_at(chess.D1), chess.Piece(chess.QUEEN, chess.WHITE))
        self.assertEqual(self.game.get_piece_at(chess.D8), chess.Piece(chess.QUEEN, chess.BLACK))

        # White pawns on rank 4 (a4 to h4)
        for col in range(8):
            sq = chess.square(col, 3)
            self.assertEqual(
                self.game.get_piece_at(sq),
                chess.Piece(chess.PAWN, chess.WHITE),
                f"Square {chess.square_name(sq)} must have a white pawn",
            )

        # Black pawns on rank 5 (a5 to h5)
        for col in range(8):
            sq = chess.square(col, 4)
            self.assertEqual(
                self.game.get_piece_at(sq),
                chess.Piece(chess.PAWN, chess.BLACK),
                f"Square {chess.square_name(sq)} must have a black pawn",
            )

        # Ensure no kings exist on board
        self.assertIsNone(self.game.board.king(chess.WHITE))
        self.assertIsNone(self.game.board.king(chess.BLACK))

        # Royal square query returns Queen's square
        self.assertEqual(self.game.king_square(chess.WHITE), chess.D1)
        self.assertEqual(self.game.king_square(chess.BLACK), chess.D8)

    def test_opening_legal_moves(self):
        """Pawns cannot push forward initially (blocked by enemy pawns) but can capture diagonally."""
        # a4 pawn: blocked at a5, can capture diagonally at b5
        a4_dests = self.game.get_legal_destinations(chess.A4)
        self.assertNotIn(chess.A5, a4_dests)
        self.assertIn(chess.B5, a4_dests)

        # d4 pawn: can capture c5 or e5
        d4_dests = self.game.get_legal_destinations(chess.D4)
        self.assertNotIn(chess.D5, d4_dests)
        self.assertIn(chess.C5, d4_dests)
        self.assertIn(chess.E5, d4_dests)

        # White Queen on d1 can maneuver along ranks/files/diagonals
        d1_dests = self.game.get_legal_destinations(chess.D1)
        self.assertIn(chess.D2, d1_dests)
        self.assertIn(chess.D3, d1_dests)
        self.assertIn(chess.C2, d1_dests)
        self.assertIn(chess.B3, d1_dests)
        self.assertIn(chess.E2, d1_dests)
        self.assertIn(chess.F3, d1_dests)

    def test_queen_capture_victory(self):
        """Capturing the opponent's Queen results in an immediate victory."""
        # Setup board where White Queen can immediately capture Black Queen
        self.game.board = chess.Board("3q4/8/8/8/8/8/8/3Q4 w - - 0 1")
        res = self.game.make_move(chess.D1, chess.D8)
        self.assertTrue(res.success)
        self.assertEqual(res.captured_piece, chess.Piece(chess.QUEEN, chess.BLACK))

        self.assertTrue(self.game.is_game_over())
        self.assertEqual(self.game.winner(), chess.WHITE)
        self.assertIn("Queen Captured!", self.game.game_over_reason())
        self.assertIn("White wins", self.game.game_over_reason())

    def test_pawn_promotion(self):
        """Pawns that reach the opponent's back rank promote properly."""
        # White pawn on a7
        self.game.board = chess.Board("3q4/P7/8/8/8/8/8/3Q4 w - - 0 1")
        self.assertTrue(self.game.needs_promotion(chess.A7, chess.A8))
        res = self.game.make_move(chess.A7, chess.A8, promotion=chess.QUEEN)
        self.assertTrue(res.success)
        self.assertTrue(res.is_promotion)
        self.assertEqual(self.game.get_piece_at(chess.A8), chess.Piece(chess.QUEEN, chess.WHITE))
        self.assertEqual(self.mode.get_queen_count(self.game, chess.WHITE), 2)

    def test_queen_danger_alert(self):
        """Direct threats to the Queen trigger in-check / danger alerts."""
        # Board where Black Queen attacks White Queen on d1
        self.game.board = chess.Board("8/8/8/8/8/8/8/3q3Q w - - 0 1")
        self.assertTrue(self.game.is_in_check())
        self.assertTrue(self.mode.is_queen_under_attack(self.game, chess.WHITE))
        self.assertIn("Danger!", self.game.status_summary())

    def test_game_reset_restores_layout(self):
        """Calling reset() properly restores the initial Queen Pawn layout."""
        self.game.make_move(chess.D4, chess.E5)
        self.assertNotEqual(self.game.to_fen(), QueenPawnMode.INITIAL_FEN)

        self.game.reset()
        self.assertEqual(self.game.to_fen(), QueenPawnMode.INITIAL_FEN)
        self.assertFalse(self.game.is_game_over())
        self.assertIsNone(self.game.winner())


if __name__ == "__main__":
    unittest.main()
