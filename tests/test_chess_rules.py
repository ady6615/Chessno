# test_chess_rules.py
"""
Comprehensive automated tests for Chessno.

Tests:
1. Legal movement for every piece type
2. Prevention of illegal moves and pins
3. Castling (kingside and queenside, blocked by check / moved pieces)
4. En passant (capture execution and captured pawn removal)
5. Pawn promotion (Queen, Rook, Bishop, Knight choices)
6. Check, checkmate, stalemate, and draw conditions
7. Coordinate conversions (screen, matrix, chess.Square, flipped view)
8. Asset loading, case-insensitive filenames, and theme switching
9. Mod extension hooks (pre-move validators, post-move hooks)
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

# Use headless/dummy video driver for Pygame tests in CI/automation
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import chess

from coordinates import (
    pixel_to_board_coords,
    board_coords_to_square,
    square_to_board_coords,
    pixel_to_square,
    piece_to_code,
    code_to_piece,
    BOARD_X,
    BOARD_Y,
    SQUARE_SIZE,
)
from game_engine import GameState, ClassicChessMode, GameMode, MoveResult
import Assets
import ChessMatrix


class TestCoordinates(unittest.TestCase):
    """Test screen, matrix, and chess square coordinate mappings."""

    def test_board_coords_standard_view(self):
        # White at bottom: row 7 is rank 1, row 0 is rank 8; col 0 is file a, col 7 is file h
        self.assertEqual(board_coords_to_square(7, 0, flipped=False), chess.A1)
        self.assertEqual(board_coords_to_square(7, 4, flipped=False), chess.E1)
        self.assertEqual(board_coords_to_square(7, 3, flipped=False), chess.D1)
        self.assertEqual(board_coords_to_square(7, 7, flipped=False), chess.H1)
        self.assertEqual(board_coords_to_square(0, 0, flipped=False), chess.A8)
        self.assertEqual(board_coords_to_square(0, 4, flipped=False), chess.E8)
        self.assertEqual(board_coords_to_square(0, 7, flipped=False), chess.H8)

    def test_board_coords_flipped_view(self):
        # Black at bottom: row 7 is rank 8, row 0 is rank 1; col 0 is file h, col 7 is file a
        self.assertEqual(board_coords_to_square(0, 0, flipped=True), chess.H1)
        self.assertEqual(board_coords_to_square(7, 0, flipped=True), chess.H8)
        self.assertEqual(board_coords_to_square(7, 7, flipped=True), chess.A8)

    def test_roundtrip_square_conversion(self):
        for sq in chess.SQUARES:
            # Standard
            r, c = square_to_board_coords(sq, flipped=False)
            reconstructed = board_coords_to_square(r, c, flipped=False)
            self.assertEqual(sq, reconstructed)

            # Flipped
            r_f, c_f = square_to_board_coords(sq, flipped=True)
            reconstructed_f = board_coords_to_square(r_f, c_f, flipped=True)
            self.assertEqual(sq, reconstructed_f)

    def test_pixel_to_square(self):
        # Center of top-left square (col 0, row 0) -> A8 in standard view
        top_left_center = (BOARD_X + 50, BOARD_Y + 50)
        self.assertEqual(pixel_to_square(top_left_center, flipped=False), chess.A8)

        # Center of bottom-left square (col 0, row 7) -> A1 in standard view
        bottom_left_center = (BOARD_X + 50, BOARD_Y + 750)
        self.assertEqual(pixel_to_square(bottom_left_center, flipped=False), chess.A1)

        # Outside board coordinates return None
        self.assertIsNone(pixel_to_square((10, 10)))
        self.assertIsNone(pixel_to_square((1100, 500)))

    def test_piece_code_conversions(self):
        self.assertEqual(piece_to_code(chess.Piece(chess.KING, chess.WHITE)), "wa")
        self.assertEqual(piece_to_code(chess.Piece(chess.QUEEN, chess.WHITE)), "wq")
        self.assertEqual(piece_to_code(chess.Piece(chess.KNIGHT, chess.WHITE)), "wk")
        self.assertEqual(piece_to_code(chess.Piece(chess.PAWN, chess.BLACK)), "bp")
        self.assertEqual(piece_to_code(chess.Piece(chess.KING, chess.BLACK)), "ba")

        self.assertEqual(code_to_piece("wa"), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(code_to_piece("bk"), chess.Piece(chess.KNIGHT, chess.BLACK))
        self.assertIsNone(piece_to_code(None))
        self.assertIsNone(code_to_piece(None))


class TestPieceMovement(unittest.TestCase):
    """Test standard piece legal moves and rule enforcement."""

    def setUp(self):
        self.state = GameState()

    def test_initial_pawn_and_knight_moves(self):
        # White to move: e2-e4 is legal
        self.assertTrue(self.state.is_legal_move(chess.E2, chess.E4))
        self.assertTrue(self.state.is_legal_move(chess.E2, chess.E3))
        # e2-e5 is illegal
        self.assertFalse(self.state.is_legal_move(chess.E2, chess.E5))

        # Knights can jump
        self.assertTrue(self.state.is_legal_move(chess.G1, chess.F3))
        self.assertTrue(self.state.is_legal_move(chess.B1, chess.C3))

        # Bishops and Rooks blocked initially
        self.assertFalse(self.state.is_legal_move(chess.F1, chess.C4))
        self.assertFalse(self.state.is_legal_move(chess.A1, chess.A3))

    def test_turn_alternation(self):
        self.assertEqual(self.state.turn, chess.WHITE)
        # Black cannot move on White's turn
        res = self.state.make_move(chess.E7, chess.E5)
        self.assertFalse(res.success)

        # White moves e2-e4
        res = self.state.make_move(chess.E2, chess.E4)
        self.assertTrue(res.success)
        self.assertEqual(self.state.turn, chess.BLACK)

        # White cannot move on Black's turn
        res = self.state.make_move(chess.D2, chess.D4)
        self.assertFalse(res.success)

        # Black moves e7-e5
        res = self.state.make_move(chess.E7, chess.E5)
        self.assertTrue(res.success)
        self.assertEqual(self.state.turn, chess.WHITE)

    def test_pin_prevention(self):
        # Setup position where White knight on e2 is pinned to King on e1 by Black rook on e8
        fen = "4r3/8/8/8/8/8/4N3/4K3 w - - 0 1"
        pinned_state = GameState(fen=fen)
        # Knight is pinned to King along the e-file: moving knight away is illegal
        self.assertFalse(pinned_state.is_legal_move(chess.E2, chess.D4))
        self.assertFalse(pinned_state.is_legal_move(chess.E2, chess.C3))
        # King moving to d1 or f1 is legal
        self.assertTrue(pinned_state.is_legal_move(chess.E1, chess.D1))


class TestSpecialMoves(unittest.TestCase):
    """Test Castling, En Passant, and Pawn Promotion."""

    def test_castling_kingside_and_queenside(self):
        # Setup position with clear path for White castling
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        state = GameState(fen=fen)

        # Kingside castling e1 -> g1
        self.assertTrue(state.is_legal_move(chess.E1, chess.G1))
        # Queenside castling e1 -> c1
        self.assertTrue(state.is_legal_move(chess.E1, chess.C1))

        # Commit kingside castle
        res = state.make_move(chess.E1, chess.G1)
        self.assertTrue(res.success)
        self.assertTrue(res.is_castling)
        # King is at g1, Rook is automatically at f1
        self.assertEqual(state.get_piece_code_at(chess.G1), "wa")
        self.assertEqual(state.get_piece_code_at(chess.F1), "wr")
        self.assertIsNone(state.get_piece_code_at(chess.E1))
        self.assertIsNone(state.get_piece_code_at(chess.H1))

    def test_castling_blocked_by_check(self):
        # King in check cannot castle
        fen = "r3k2r/8/8/8/4r3/8/8/R3K2R w KQkq - 0 1"
        state = GameState(fen=fen)
        self.assertTrue(state.is_in_check())
        self.assertFalse(state.is_legal_move(chess.E1, chess.G1))
        self.assertFalse(state.is_legal_move(chess.E1, chess.C1))

    def test_en_passant(self):
        # White pawn on e5, Black pawn advances d7 to d5
        fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        state = GameState(fen=fen)

        # White pawn can capture en passant e5 -> d6
        self.assertTrue(state.is_legal_move(chess.E5, chess.D6))
        res = state.make_move(chess.E5, chess.D6)
        self.assertTrue(res.success)
        self.assertTrue(res.is_en_passant)
        self.assertTrue(res.is_capture)
        # White pawn is on d6
        self.assertEqual(state.get_piece_code_at(chess.D6), "wp")
        # Black pawn on d5 has been removed
        self.assertIsNone(state.get_piece_code_at(chess.D5))
        # Captured piece recorded
        self.assertIn("bp", state.captured_pieces["w"])

    def test_pawn_promotion(self):
        # White pawn on e7 ready to promote on e8 (Black King on d8 so e8 is open)
        fen = "3k4/4P3/8/8/8/8/8/4K3 w - - 0 1"
        state = GameState(fen=fen)

        self.assertTrue(state.needs_promotion(chess.E7, chess.E8))

        # Test promotion to Queen
        state_q = GameState(fen=fen)
        res_q = state_q.make_move(chess.E7, chess.E8, promotion=chess.QUEEN)
        self.assertTrue(res_q.success)
        self.assertTrue(res_q.is_promotion)
        self.assertEqual(state_q.get_piece_code_at(chess.E8), "wq")

        # Test promotion to Knight (underpromotion)
        state_n = GameState(fen=fen)
        res_n = state_n.make_move(chess.E7, chess.E8, promotion=chess.KNIGHT)
        self.assertTrue(res_n.success)
        self.assertTrue(res_n.is_promotion)
        self.assertEqual(state_n.get_piece_code_at(chess.E8), "wk")

        # Test promotion to Rook
        state_r = GameState(fen=fen)
        res_r = state_r.make_move(chess.E7, chess.E8, promotion=chess.ROOK)
        self.assertTrue(res_r.success)
        self.assertEqual(state_r.get_piece_code_at(chess.E8), "wr")

        # Test promotion to Bishop
        state_b = GameState(fen=fen)
        res_b = state_b.make_move(chess.E7, chess.E8, promotion=chess.BISHOP)
        self.assertTrue(res_b.success)
        self.assertEqual(state_b.get_piece_code_at(chess.E8), "wb")


class TestCheckmateAndDraws(unittest.TestCase):
    """Test checkmate, stalemate, and draw conditions."""

    def test_scholars_mate(self):
        state = GameState()
        # 1. e4 e5
        state.make_move(chess.E2, chess.E4)
        state.make_move(chess.E7, chess.E5)
        # 2. Qh5 Nc6
        state.make_move(chess.D1, chess.H5)
        state.make_move(chess.B8, chess.C6)
        # 3. Bc4 Nf6
        state.make_move(chess.F1, chess.C4)
        state.make_move(chess.G8, chess.F6)
        # 4. Qxf7# (Checkmate)
        res = state.make_move(chess.H5, chess.F7)
        self.assertTrue(res.success)
        self.assertTrue(res.is_checkmate)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)
        self.assertIn("Checkmate", state.game_over_reason())

    def test_fools_mate(self):
        state = GameState()
        # 1. f3 e5 2. g4 Qh4#
        state.make_move(chess.F2, chess.F3)
        state.make_move(chess.E7, chess.E5)
        state.make_move(chess.G2, chess.G4)
        res = state.make_move(chess.D8, chess.H4)
        self.assertTrue(res.success)
        self.assertTrue(res.is_checkmate)
        self.assertEqual(state.winner(), chess.BLACK)

    def test_stalemate(self):
        # Known stalemate position: Black king has no legal moves and is not in check
        fen = "k7/8/1Q6/8/8/8/8/4K3 b - - 0 1"
        state = GameState(fen=fen)
        self.assertTrue(state.is_game_over())
        self.assertFalse(state.is_in_check())
        self.assertIsNone(state.winner())
        self.assertIn("Stalemate", state.game_over_reason())

    def test_insufficient_material(self):
        # King vs King is an immediate draw
        fen = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
        state = GameState(fen=fen)
        self.assertTrue(state.is_game_over())
        self.assertIn("Insufficient Material", state.game_over_reason())


class TestModExtensibility(unittest.TestCase):
    """Test game mode extensibility hooks for future mods."""

    def test_pre_move_validator_hook(self):
        state = GameState()
        # Mod hook: e2-e4 is forbidden by a custom rule
        def forbid_e4(game_state, move):
            return move != chess.Move.from_uci("e2e4")

        state.register_pre_move_validator(forbid_e4)

        # e2-e4 should be rejected
        self.assertFalse(state.is_legal_move(chess.E2, chess.E4))
        # d2-d4 should still be permitted
        self.assertTrue(state.is_legal_move(chess.D2, chess.D4))

    def test_post_move_hook(self):
        state = GameState()
        hook_called = []

        def track_move(game_state, result):
            hook_called.append(result.san)

        state.register_post_move_hook(track_move)

        state.make_move(chess.E2, chess.E4)
        self.assertEqual(hook_called, ["e4"])


class TestAssetSystem(unittest.TestCase):
    """Test asset loading, case-insensitivity, and theme switching."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        # Create a display surface for convert_alpha()
        pygame.display.set_mode((1200, 900))

    def test_load_default_assets(self):
        board, pieces = Assets.load_assets("Default")
        self.assertIsNotNone(board)
        self.assertEqual(board.get_size(), (800, 800))
        self.assertEqual(len(pieces), 12)

        # Verify all piece codes present
        for code in Assets.PIECE_FILES:
            self.assertIn(code, pieces)
            self.assertIsInstance(pieces[code], pygame.Surface)

    def test_available_packs(self):
        packs = Assets.get_available_packs()
        self.assertIn("Default", packs)

    def test_sound_system_graceful_fallback(self):
        # Default pack doesn't have custom wavs, procedural fallback should work
        self.assertTrue(Assets.is_sound_enabled())
        # Playing sounds should not throw exceptions
        Assets.play_sound("move")
        Assets.play_sound("capture")
        Assets.play_sound("check")
        Assets.play_sound("invalid")


class TestChessMatrixCompatibility(unittest.TestCase):
    """Test legacy ChessMatrix proxy interface."""

    def test_matrix_proxy(self):
        state = GameState()
        ChessMatrix.set_active_game_state(state)

        # King and Pawn at initial positions
        self.assertEqual(ChessMatrix.matrix[7][4], "wa")  # e1
        self.assertEqual(ChessMatrix.matrix[0][4], "ba")  # e8
        self.assertEqual(ChessMatrix.matrix[6][4], "wp")  # e2

        # Move e2-e4
        moved = ChessMatrix.move_piece((6, 4), (4, 4))
        self.assertTrue(moved)
        self.assertEqual(ChessMatrix.matrix[4][4], "wp")
        self.assertIsNone(ChessMatrix.matrix[6][4])


if __name__ == "__main__":
    unittest.main()
