# test_bishop_dash.py
"""
Unit tests for the 'Bishop Dash' game mode in Chessno.

Rules Tested:
1. Initial Board Setup:
   - Exactly 2 Bishops, 8 Pawns, and 1 King per player at default positions.
   - 0 Knights, 0 Rooks, 0 Queens.
   - White bishops at c1 and f1; Black bishops at c8 and f8.
2. Bishop 4-Way Diagonal Dashing:
   - Exactly 4 diagonal directions (Up-Left, Up-Right, Down-Left, Down-Right).
   - Dashes until board boundary.
   - Obstructed by own colour pawn/king/bishop (stops right before).
   - Hits and captures enemy piece.
   - Cannot stop at intermediate squares along the diagonal ray.
3. Pawn Promotion:
   - Pawns can ONLY promote to Bishops.
   - Auto-promotion defaults to chess.BISHOP.
   - Promoted Bishop becomes a dashing bishop.
4. Win Condition:
   - First to deliver checkmate wins.
   - Stalemate and draw detection.
5. AI Bot Integration:
   - Bot selects legal dash moves and evaluates Bishop Dash positions.
6. Visual Animation & Laser Highlights:
   - High-speed dash animation with royal amethyst/violet theme.
   - Diagonal trajectory beams on bishop selection.
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
from bishop_dash_engine import BishopDashMode
from ai_bot import BotDifficulty, select_best_move, evaluate_board


class TestBishopDashMode(unittest.TestCase):
    def setUp(self):
        self.mode = BishopDashMode()
        self.state = GameState(mode=self.mode)

    def test_initial_board_pieces_setup(self):
        """Verify initial layout: only 2 bishops, 8 pawns, 1 king per player at default positions."""
        board = self.state.board
        # White pieces
        self.assertEqual(len(board.pieces(chess.BISHOP, chess.WHITE)), 2)
        self.assertEqual(len(board.pieces(chess.PAWN, chess.WHITE)), 8)
        self.assertEqual(len(board.pieces(chess.KING, chess.WHITE)), 1)
        self.assertEqual(len(board.pieces(chess.KNIGHT, chess.WHITE)), 0)
        self.assertEqual(len(board.pieces(chess.ROOK, chess.WHITE)), 0)
        self.assertEqual(len(board.pieces(chess.QUEEN, chess.WHITE)), 0)

        # Black pieces
        self.assertEqual(len(board.pieces(chess.BISHOP, chess.BLACK)), 2)
        self.assertEqual(len(board.pieces(chess.PAWN, chess.BLACK)), 8)
        self.assertEqual(len(board.pieces(chess.KING, chess.BLACK)), 1)
        self.assertEqual(len(board.pieces(chess.KNIGHT, chess.BLACK)), 0)
        self.assertEqual(len(board.pieces(chess.ROOK, chess.BLACK)), 0)
        self.assertEqual(len(board.pieces(chess.QUEEN, chess.BLACK)), 0)

        # Squares check
        self.assertEqual(board.piece_at(chess.C1), chess.Piece(chess.BISHOP, chess.WHITE))
        self.assertEqual(board.piece_at(chess.F1), chess.Piece(chess.BISHOP, chess.WHITE))
        self.assertEqual(board.piece_at(chess.E1), chess.Piece(chess.KING, chess.WHITE))
        self.assertEqual(board.piece_at(chess.C8), chess.Piece(chess.BISHOP, chess.BLACK))
        self.assertEqual(board.piece_at(chess.F8), chess.Piece(chess.BISHOP, chess.BLACK))
        self.assertEqual(board.piece_at(chess.E8), chess.Piece(chess.KING, chess.BLACK))

    def test_initial_bishop_dash_blocked_by_pawns(self):
        """At start, White Bishops at c1 and f1 are completely surrounded by pawns and board edges."""
        dests_c1 = self.mode.get_bishop_dash_destinations(self.state.board, chess.C1)
        # Up-Left (b2 pawn), Up-Right (d2 pawn), Down-Left/Down-Right (off board)
        self.assertEqual(dests_c1, [])

        dests_f1 = self.mode.get_bishop_dash_destinations(self.state.board, chess.F1)
        # Up-Left (e2 pawn), Up-Right (g2 pawn), Down-Left/Down-Right (off board)
        self.assertEqual(dests_f1, [])

    def test_bishop_dash_after_pawn_move(self):
        """After 1. e4, the f1 bishop has an open diagonal towards a6."""
        self.state.make_move(chess.E2, chess.E4)
        dests = self.mode.get_bishop_dash_destinations(self.state.board, chess.F1)
        # Diagonal Up-Left: f1 -> e2 -> d3 -> c4 -> b5 -> a6 (edge)
        self.assertIn(chess.A6, dests)

    def test_bishop_dash_cannot_stop_at_intermediate_squares(self):
        """Bishop cannot stop at intermediate squares (e2, d3, c4, b5), must dash all the way to a6."""
        self.state.make_move(chess.E2, chess.E4)
        self.state.make_move(chess.E7, chess.E5)

        self.assertFalse(self.state.is_legal_move(chess.F1, chess.E2))
        self.assertFalse(self.state.is_legal_move(chess.F1, chess.D3))
        self.assertFalse(self.state.is_legal_move(chess.F1, chess.C4))
        self.assertFalse(self.state.is_legal_move(chess.F1, chess.B5))
        self.assertTrue(self.state.is_legal_move(chess.F1, chess.A6))

    def test_bishop_dash_to_board_boundaries_in_4_directions(self):
        """On an open board, bishop dashes in all 4 diagonal directions all the way to board edges."""
        # White Bishop at d4, White King at h1, Black King at h8
        b = chess.Board("7k/8/8/8/3B4/8/8/7K w - - 0 1")
        dests = self.mode.get_bishop_dash_destinations(b, chess.D4)
        # Up-Right:   d4 -> e5 -> f6 -> g7 -> h8? (Black King is at h8 -> captured!)
        # Up-Left:    d4 -> c5 -> b6 -> a7 (board edge)
        # Down-Left:  d4 -> c3 -> b2 -> a1 (board edge)
        # Down-Right: d4 -> e3 -> f2 -> g1 (board edge)
        expected = {chess.H8, chess.A7, chess.A1, chess.G1}
        self.assertEqual(set(dests), expected)

    def test_bishop_dash_stopped_before_friendly_piece(self):
        """Bishop stops immediately before a friendly piece along its diagonal path."""
        # White Bishop at d4, friendly White Pawn at f6
        b = chess.Board("7k/8/5P2/8/3B4/8/8/7K w - - 0 1")
        dests = self.mode.get_bishop_dash_destinations(b, chess.D4)
        # In Up-Right ray: e5 is empty, f6 has friendly pawn -> stops at e5
        self.assertIn(chess.E5, dests)
        self.assertNotIn(chess.F6, dests)
        self.assertNotIn(chess.G7, dests)

    def test_bishop_dash_hits_and_captures_enemy_piece(self):
        """Bishop hits the first enemy piece along its diagonal path and captures it."""
        # White Bishop at d4, enemy Black Pawn at f6
        b = chess.Board("7k/8/5p2/8/3B4/8/8/7K w - - 0 1")
        dests = self.mode.get_bishop_dash_destinations(b, chess.D4)
        # In Up-Right ray: hits Black pawn at f6 -> captures at f6
        self.assertIn(chess.F6, dests)
        self.assertNotIn(chess.E5, dests)
        self.assertNotIn(chess.G7, dests)

    def test_pawn_promotion_strictly_to_bishop(self):
        """Pawns can ONLY promote to Bishops in Bishop Dash."""
        b = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        # Promotion to Queen must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.QUEEN), board=b))
        # Promotion to Rook must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.ROOK), board=b))
        # Promotion to Knight must be rejected
        self.assertFalse(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.KNIGHT), board=b))
        # Promotion to Bishop must be accepted
        self.assertTrue(self.mode.can_move(None, chess.Move(chess.E7, chess.E8, promotion=chess.BISHOP), board=b))

    def test_game_state_auto_promotes_to_bishop(self):
        """GameState defaults pawn promotion to chess.BISHOP in Bishop Dash."""
        state = GameState(mode=self.mode)
        state.board = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        res = state.make_move(chess.E7, chess.E8)
        self.assertTrue(res.success)
        promoted_piece = state.board.piece_at(chess.E8)
        self.assertIsNotNone(promoted_piece)
        self.assertEqual(promoted_piece.piece_type, chess.BISHOP)

    def test_promoted_bishop_becomes_dashing_bishop(self):
        """Once promoted to Bishop, the piece dashes following Bishop Dash diagonal rules."""
        state = GameState(mode=self.mode)
        state.board = chess.Board("7k/4P3/8/8/8/8/8/7K w - - 0 1")
        state.make_move(chess.E7, chess.E8)  # promotes to Bishop at e8
        # Black king moves to h7
        state.make_move(chess.H8, chess.H7)
        # White bishop at e8 can dash Down-Left to a4 (e8 -> d7 -> c6 -> b5 -> a4)
        dests = self.mode.get_bishop_dash_destinations(state.board, chess.E8)
        self.assertIn(chess.A4, dests)

    def test_checkmate_detection_in_bishop_dash(self):
        """A player whose King is in check with no valid moves is checkmated."""
        state = GameState(mode=self.mode)
        # Position: Black King cornered at a8
        # White King at a6 covers a7 and b7
        # White Bishop at h1 gives check to a8 along long diagonal
        # White Bishop at g3 covers b8 escape square
        state.board = chess.Board("k7/8/K7/8/8/6B1/8/7B b - - 0 1")
        self.assertTrue(state.board.is_check())
        self.assertTrue(self.mode.is_game_over(state))
        self.assertEqual(self.mode.winner(state), chess.WHITE)
        self.assertIn("Checkmate", self.mode.game_over_reason(state))

    def test_ai_bot_selects_bishop_dash_moves(self):
        """AI bot generates and selects legal Bishop Dash moves across difficulties."""
        state = GameState(mode=self.mode)
        for diff in (BotDifficulty.NOVICE, BotDifficulty.CASUAL, BotDifficulty.INTERMEDIATE, BotDifficulty.MASTER):
            chosen = select_best_move(state.board, diff, game_mode=self.mode)
            self.assertIsNotNone(chosen)
            self.assertTrue(self.mode.can_move(state, chosen))

    def test_ai_bot_evaluation_in_bishop_dash(self):
        """evaluate_board computes sensible scores for Bishop Dash material and check."""
        b = chess.Board("2b1kb2/pppppppp/8/8/8/8/PPPPPPPP/2B1KB2 w - - 0 1")
        score_equal = evaluate_board(b, game_mode=self.mode)
        self.assertEqual(score_equal, 0)

    def test_bishop_dash_animation_rendering(self):
        """Verify ChessRenderer handles bishop dash animation triggers and drawing cleanly."""
        import pygame
        from renderer import ChessRenderer
        import Assets

        pygame.init()
        pygame.font.init()
        surface = pygame.Surface((1200, 900))
        renderer = ChessRenderer(surface)
        _, piece_images = Assets.load_assets("Default")

        state = GameState(mode=self.mode)
        self.assertFalse(renderer.is_dash_animating())

        # Trigger bishop dash (amethyst violet theme)
        renderer.trigger_bishop_dash(
            from_sq=chess.C1,
            to_sq=chess.A3,
            piece_code="wb",
            piece_images=piece_images,
            is_capture=False,
            flipped=False,
        )
        self.assertTrue(renderer.is_dash_animating())
        self.assertEqual(renderer.rook_dash_anim.theme_color, (185, 85, 255))

        # Render during dash
        renderer.draw_pieces(state, piece_images, flipped=False)
        renderer.draw_rook_dash_animation(piece_images)

        # Advance into impact phase
        renderer.update_rook_dash(0.18)
        renderer.draw_rook_dash_animation(piece_images)

        # Advance to completion
        finished = renderer.update_rook_dash(0.20)
        self.assertTrue(finished)
        self.assertFalse(renderer.is_dash_animating())

    def test_bishop_dash_laser_highlights(self):
        """Verify laser trajectory highlight beams render when a Bishop is selected in Bishop Dash."""
        import pygame
        from renderer import ChessRenderer
        import Assets

        surface = pygame.Surface((1200, 900))
        renderer = ChessRenderer(surface)

        # White bishop at d4 with dash destinations
        self.state.board = chess.Board("7k/8/8/8/3B4/8/8/7K w - - 0 1")
        dests = self.state.get_legal_destinations(chess.D4)
        self.assertGreater(len(dests), 0)

        # Draw highlights with bishop selected - should draw violet diagonal beams without error
        renderer.draw_highlights(
            game_state=self.state,
            selected_square=chess.D4,
            legal_destinations=dests,
            flipped=False,
        )


if __name__ == "__main__":
    unittest.main()
