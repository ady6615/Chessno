# test_atomic_mode.py
"""
Comprehensive Unit Tests for Atomic Chess Mode in Chessno.

Verifies:
1. Setup and Initialization:
   - Standard 32-piece initial chess layout.
   - Authoritative chess.variant.AtomicBoard integration.
   - Mode identification ("Atomic Chess").
2. Core Explosion Mechanics:
   - Capturing piece is destroyed and removed.
   - Captured piece is destroyed and removed.
   - Adjacent non-pawn pieces of BOTH colors within 1 Chebyshev distance are destroyed.
   - Surrounding pawns are completely immune and survive the explosion blast.
   - En passant capture triggers explosion centered on the destination square.
   - Non-capturing moves leave surrounding pieces intact.
3. Victory & Game Over Conditions:
   - King explosion (Atomic Blast): Capturing a piece adjacent to opponent's King wins instantly.
   - Correct winner, is_game_over(), and game_over_reason() reporting.
   - Traditional checkmate win.
4. Rule Constraints & Suicide Prevention:
   - Suicidal captures (exploding one's own King) are strictly illegal.
   - Kings are prohibited from capturing any piece.
5. Renderer & UI:
   - 8-card mode selector layout.
   - Explosion animation lifecycle, update, cancel, and drawing.
6. Bot Controller compatibility:
   - Evaluator and move selector recognize instant variant win opportunities.
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

os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import chess
import chess.variant

from game_engine import GameState
from atomic_engine import AtomicChessMode
from renderer import ChessRenderer
from ai_bot import ChessBotController, BotDifficulty, evaluate_board


class TestAtomicChessMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.renderer = ChessRenderer(
            screen=cls.screen,
            board_x=50,
            board_y=50,
            square_size=100,
            panel_x=900,
            panel_width=270,
        )

    def setUp(self):
        self.mode = AtomicChessMode()
        self.game_state = GameState(mode=self.mode)

    def test_initial_board_setup(self):
        """Verify atomic mode initializes with standard layout and AtomicBoard instance."""
        self.assertEqual(self.mode.name, "Atomic Chess")
        self.assertIsInstance(self.game_state.board, chess.variant.AtomicBoard)
        self.assertEqual(self.game_state.turn, chess.WHITE)
        self.assertEqual(len(self.game_state.board.piece_map()), 32)
        self.assertFalse(self.game_state.is_game_over())
        self.assertIsNone(self.game_state.winner())

    def test_capture_explosion_removes_capturer_captured_and_adjacent_non_pawns(self):
        """Verify that a capture destroys capturer, captured, and adjacent non-pawns, sparing pawns."""
        # Custom board layout around d5
        # d5: black knight (captured)
        # c3: white knight (capturing)
        # d6: black bishop (adjacent non-pawn -> destroyed)
        # c5: white rook (adjacent non-pawn -> destroyed)
        # c6: black pawn (adjacent pawn -> survives!)
        # e6: white pawn (adjacent pawn -> survives!)
        board = self.game_state.board
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.C3, chess.Piece(chess.KNIGHT, chess.WHITE))
        board.set_piece_at(chess.D5, chess.Piece(chess.KNIGHT, chess.BLACK))
        board.set_piece_at(chess.D6, chess.Piece(chess.BISHOP, chess.BLACK))
        board.set_piece_at(chess.C5, chess.Piece(chess.ROOK, chess.WHITE))
        board.set_piece_at(chess.C6, chess.Piece(chess.PAWN, chess.BLACK))
        board.set_piece_at(chess.E6, chess.Piece(chess.PAWN, chess.WHITE))

        res = self.game_state.make_move(chess.C3, chess.D5)
        self.assertTrue(res.success)
        self.assertTrue(res.is_capture)

        # Capturing piece (white knight) and captured piece (black knight) destroyed
        self.assertIsNone(board.piece_at(chess.C3))
        self.assertIsNone(board.piece_at(chess.D5))

        # Adjacent non-pawns (black bishop on d6 and white rook on c5) destroyed
        self.assertIsNone(board.piece_at(chess.D6))
        self.assertIsNone(board.piece_at(chess.C5))

        # Adjacent pawns (c6 and e6) must survive
        p_c6 = board.piece_at(chess.C6)
        self.assertIsNotNone(p_c6)
        self.assertEqual(p_c6.piece_type, chess.PAWN)
        self.assertEqual(p_c6.color, chess.BLACK)

        p_e6 = board.piece_at(chess.E6)
        self.assertIsNotNone(p_e6)
        self.assertEqual(p_e6.piece_type, chess.PAWN)
        self.assertEqual(p_e6.color, chess.WHITE)

    def test_non_capture_move_causes_no_explosion(self):
        """Verify normal moves advance peacefully without destroying surrounding pieces."""
        res = self.game_state.make_move(chess.E2, chess.E4)
        self.assertTrue(res.success)
        self.assertFalse(res.is_capture)
        self.assertIsNone(self.mode.last_explosion)
        # Pawn sits on e4, pawns on d2 and f2 remain untouched
        self.assertIsNotNone(self.game_state.board.piece_at(chess.E4))
        self.assertIsNotNone(self.game_state.board.piece_at(chess.D2))
        self.assertIsNotNone(self.game_state.board.piece_at(chess.F2))

    def test_king_blown_up_wins_game(self):
        """Verify that blowing up the opponent's king results in an immediate victory."""
        # 1. Nf3 d5 2. Ne5 f6 3. Nf7 e5 4. Nxd8# (captures Queen on d8, King on e8 is adjacent)
        moves = [
            (chess.G1, chess.F3),
            (chess.D7, chess.D5),
            (chess.F3, chess.E5),
            (chess.F7, chess.F6),
            (chess.E5, chess.F7),
            (chess.E7, chess.E5),
            (chess.F7, chess.D8),  # Nxd8 explodes Queen and adjacent King on e8!
        ]
        for f, t in moves:
            res = self.game_state.make_move(f, t)
            self.assertTrue(res.success)

        self.assertTrue(self.game_state.is_game_over())
        self.assertEqual(self.game_state.winner(), chess.WHITE)
        self.assertIn("Atomic Blast", self.game_state.game_over_reason())
        self.assertIn("Black King was blown up", self.game_state.game_over_reason())
        self.assertIn("White wins", self.game_state.game_over_reason())

    def test_suicidal_capture_is_illegal(self):
        """Verify a player cannot make a capture that would explode their own king."""
        board = self.game_state.board
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.E2, chess.Piece(chess.ROOK, chess.WHITE))
        board.set_piece_at(chess.E3, chess.Piece(chess.KNIGHT, chess.BLACK))

        # Rook on e2 capturing knight on e3:
        # e3 is adjacent to e2, but e2 is adjacent to e1 (White King)!
        # If e3 explodes, e2, d2, f2, e4, d4, f4, d3, f3 explode. e1 is adjacent to e2, not e3.
        # But wait! If White King is on e2 and black piece is on d2:
        # Let's place White King on e2 and black piece on d2:
        board.clear()
        board.set_piece_at(chess.E1, chess.Piece(chess.ROOK, chess.WHITE))
        board.set_piece_at(chess.D1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.E2, chess.Piece(chess.KNIGHT, chess.BLACK))

        # Rook on e1 capturing knight on e2:
        # e2 is directly adjacent to d1 (White King on d1: Chebyshev distance = 1)!
        # Exploding e2 would destroy White King on d1!
        m = chess.Move(chess.E1, chess.E2)
        self.assertNotIn(m, board.legal_moves)
        res = self.game_state.make_move(chess.E1, chess.E2)
        self.assertFalse(res.success)

    def test_king_cannot_capture(self):
        """Verify King cannot capture any piece because capturing piece explodes."""
        board = self.game_state.board
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.E2, chess.Piece(chess.PAWN, chess.BLACK))

        # King on e1 attempting to capture pawn on e2:
        m = chess.Move(chess.E1, chess.E2)
        self.assertNotIn(m, board.legal_moves)
        res = self.game_state.make_move(chess.E1, chess.E2)
        self.assertFalse(res.success)

    def test_checkmate_game_over(self):
        """Verify traditional checkmate also triggers game over."""
        # Fool's mate: 1. f3 e5 2. g4 Qh4#
        moves = [
            (chess.F2, chess.F3),
            (chess.E7, chess.E5),
            (chess.G2, chess.G4),
            (chess.D8, chess.H4),
        ]
        for f, t in moves:
            res = self.game_state.make_move(f, t)
            self.assertTrue(res.success)

        self.assertTrue(self.game_state.is_game_over())
        self.assertEqual(self.game_state.winner(), chess.BLACK)
        self.assertIn("Checkmate", self.game_state.game_over_reason())

    def test_en_passant_explosion(self):
        """Verify en passant capture triggers explosion centered on destination square."""
        # 1. e4 a6 2. e5 d5 3. exd6 (EP capture on d6)
        self.game_state.make_move(chess.E2, chess.E4)
        self.game_state.make_move(chess.A7, chess.A6)
        self.game_state.make_move(chess.E4, chess.E5)
        self.game_state.make_move(chess.D7, chess.D5)
        res = self.game_state.make_move(chess.E5, chess.D6)
        self.assertTrue(res.success)
        self.assertTrue(res.is_capture)
        self.assertTrue(res.is_en_passant)

        # In atomic chess, both capturing pawn on d6 and captured pawn on d5 explode
        self.assertIsNone(self.game_state.board.piece_at(chess.D6))
        self.assertIsNone(self.game_state.board.piece_at(chess.D5))

    def test_mode_selector_modal_rects_and_render(self):
        """Verify renderer has 9 mode selector rects and renders Atomic modal card."""
        rects = self.renderer.get_mode_selector_rects()
        self.assertEqual(len(rects), 9)
        rect_atomic = rects[7]
        self.assertGreater(rect_atomic.width, 0)
        self.assertGreater(rect_atomic.height, 0)

        # Modal rendering executes without error
        ret_rects = self.renderer.draw_mode_selector_modal(mouse_pos=(600, 300))
        self.assertEqual(len(ret_rects), 8)

    def test_explosion_animation_lifecycle_and_drawing(self):
        """Verify AtomicExplosionAnimation trigger, update, cancel, and drawing."""
        anim = self.renderer.atomic_explosion_anim
        self.assertFalse(anim.is_active)
        self.assertFalse(self.renderer.is_explosion_animating())

        self.renderer.trigger_atomic_explosion(
            center_sq=chess.D5,
            affected_squares=[chess.D5, chess.D6, chess.C5],
            flipped=False,
        )
        self.assertTrue(anim.is_active)
        self.assertTrue(self.renderer.is_explosion_animating())
        self.assertEqual(anim.center_sq, chess.D5)

        # Drawing during animation
        self.renderer.draw_atomic_explosion()

        # Update animation until completion
        finished = self.renderer.update_atomic_explosion(0.50)
        self.assertTrue(finished)
        self.assertFalse(anim.is_active)
        self.assertFalse(self.renderer.is_explosion_animating())

    def test_bot_controller_plays_instant_atomic_blast_win(self):
        """Verify AI bot recognizes and immediately plays winning atomic capture."""
        from ai_bot import select_best_move

        board = self.game_state.board
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.D8, chess.Piece(chess.QUEEN, chess.BLACK))  # adjacent to black king
        board.set_piece_at(chess.D1, chess.Piece(chess.ROOK, chess.WHITE))

        # White Rook on d1 can play Rxd8 to blow up Black Queen and adjacent Black King!
        move = select_best_move(board, BotDifficulty.MASTER)
        self.assertIsNotNone(move)
        self.assertEqual(move, chess.Move(chess.D1, chess.D8))


if __name__ == "__main__":
    unittest.main()
