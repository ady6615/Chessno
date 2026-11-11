# test_hero_mode.py
"""
Comprehensive unit tests for 'Hero Mode' in Chessno.

Validates:
1. Initial board setup (1 Hero, 8 Pawns, 1 King per side, no Rooks/Knights/Bishops).
2. Hero piece movement as Queen AND Knight combined (Amazon piece).
3. Knight leaps over intervening pawns/pieces on move 1.
4. Capture mechanics via both Queen rays and Knight jumps.
5. Inability to land on friendly pieces.
6. Pawn movement and auto/strict promotion to Hero.
7. King movement and check evasion.
8. Check detection via both Queen rays and Knight leaps.
9. Checkmate detection and winner determination.
10. Stalemate detection.
11. Synthesized piece assets ('wh' and 'bh') in Assets.
12. UI and Modal rendering integration.
13. AI Bot decision making in Hero Mode.
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

from game_engine import GameState
from hero_mode_engine import HeroMode
from ai_bot import select_best_move, BotDifficulty
from renderer import ChessRenderer
import Assets


class TestHeroMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.board_img, cls.piece_images = Assets.load_assets("Default")
        cls.renderer = ChessRenderer(screen=cls.screen)

    def test_hero_initial_board_setup(self):
        """Verify initial board setup: 1 Hero (d1/d8), 8 Pawns, 1 King, no Rooks/Knights/Bishops."""
        mode = HeroMode()
        state = GameState(mode=mode)

        # FEN check
        self.assertEqual(state.board.fen(), "3qk3/pppppppp/8/8/8/8/PPPPPPPP/3QK3 w - - 0 1")

        # White pieces check
        w_queens = list(state.board.pieces(chess.QUEEN, chess.WHITE))
        w_kings = list(state.board.pieces(chess.KING, chess.WHITE))
        w_pawns = list(state.board.pieces(chess.PAWN, chess.WHITE))
        self.assertEqual(w_queens, [chess.D1])
        self.assertEqual(w_kings, [chess.E1])
        self.assertEqual(len(w_pawns), 8)
        self.assertEqual(len(state.board.pieces(chess.ROOK, chess.WHITE)), 0)
        self.assertEqual(len(state.board.pieces(chess.KNIGHT, chess.WHITE)), 0)
        self.assertEqual(len(state.board.pieces(chess.BISHOP, chess.WHITE)), 0)

        # Black pieces check
        b_queens = list(state.board.pieces(chess.QUEEN, chess.BLACK))
        b_kings = list(state.board.pieces(chess.KING, chess.BLACK))
        b_pawns = list(state.board.pieces(chess.PAWN, chess.BLACK))
        self.assertEqual(b_queens, [chess.D8])
        self.assertEqual(b_kings, [chess.E8])
        self.assertEqual(len(b_pawns), 8)
        self.assertEqual(len(state.board.pieces(chess.ROOK, chess.BLACK)), 0)
        self.assertEqual(len(state.board.pieces(chess.KNIGHT, chess.BLACK)), 0)
        self.assertEqual(len(state.board.pieces(chess.BISHOP, chess.BLACK)), 0)

        # Total 20 pieces
        self.assertEqual(len(state.board.piece_map()), 20)

    def test_hero_moves_on_move_one_knight_leaps(self):
        """On move 1, pawns block Queen rays forward, but Hero can leap over pawns as a Knight!"""
        mode = HeroMode()
        state = GameState(mode=mode)

        # Get legal moves for White Hero from d1
        hero_moves = state.get_legal_moves_from(chess.D1)
        hero_destinations = [m.to_square for m in hero_moves]

        # White Hero can jump to c3 and e3 (Knight jumps)
        self.assertIn(chess.C3, hero_destinations)
        self.assertIn(chess.E3, hero_destinations)

        # White Hero cannot jump to b2 or f2 because friendly pawns are there
        self.assertNotIn(chess.B2, hero_destinations)
        self.assertNotIn(chess.F2, hero_destinations)

        # Execute move d1c3
        res = state.make_move(chess.D1, chess.C3)
        self.assertTrue(res.success)
        self.assertEqual(state.board.piece_at(chess.C3), chess.Piece(chess.QUEEN, chess.WHITE))
        self.assertIsNone(state.board.piece_at(chess.D1))
        self.assertEqual(state.turn, chess.BLACK)

    def test_hero_open_board_combines_queen_and_knight(self):
        """In an open board, Hero has both Queen rays (up to 27 squares) and Knight jumps (up to 8 squares)."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # Empty board with only White Hero at d4 and Kings
        state.board = chess.Board("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")

        moves = state.get_legal_moves_from(chess.D4)
        dests = {m.to_square for m in moves}

        # Queen ray moves: ranks, files, diagonals
        self.assertIn(chess.D1, dests)
        self.assertIn(chess.D8, dests)
        self.assertIn(chess.A4, dests)
        self.assertIn(chess.H4, dests)
        self.assertIn(chess.A1, dests)
        self.assertIn(chess.G7, dests)
        self.assertIn(chess.A7, dests)
        self.assertIn(chess.G1, dests)

        # Knight jumps from d4: c6, e6, b5, f5, b3, f3, c2, e2
        knight_jumps = [chess.C6, chess.E6, chess.B5, chess.F5, chess.B3, chess.F3, chess.C2, chess.E2]
        for kj in knight_jumps:
            self.assertIn(kj, dests)

    def test_hero_knight_capture_and_queen_capture(self):
        """Verify Hero can capture enemy pieces using both Queen rays and Knight jumps."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # White Hero at d4, Black pawn at c6 (knight jump distance), Black pawn at d7 (queen ray distance)
        state.board = chess.Board("4k3/3p4/2p5/8/3Q4/8/8/4K3 w - - 0 1")

        # Test capture via Knight jump: d4xc6
        state_copy1 = GameState(mode=HeroMode())
        state_copy1.board = state.board.copy()
        res1 = state_copy1.make_move(chess.D4, chess.C6)
        self.assertTrue(res1.success)
        self.assertTrue(res1.is_capture)
        self.assertEqual(state_copy1.board.piece_at(chess.C6), chess.Piece(chess.QUEEN, chess.WHITE))

        # Test capture via Queen ray: d4xd7
        state_copy2 = GameState(mode=HeroMode())
        state_copy2.board = state.board.copy()
        res2 = state_copy2.make_move(chess.D4, chess.D7)
        self.assertTrue(res2.success)
        self.assertTrue(res2.is_capture)
        self.assertEqual(state_copy2.board.piece_at(chess.D7), chess.Piece(chess.QUEEN, chess.WHITE))

    def test_pawn_movement_and_promotion_to_hero(self):
        """Pawns move normally and promote to Hero (Queen)."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # White pawn at e7, Black King at a8, White King at e1
        state.board = chess.Board("k7/4P3/8/8/8/8/8/4K3 w - - 0 1")

        # Needs promotion
        self.assertTrue(state.needs_promotion(chess.E7, chess.E8))

        # Promote to Queen (Hero)
        res = state.make_move(chess.E7, chess.E8, promotion=chess.QUEEN)
        self.assertTrue(res.success)
        self.assertTrue(res.is_promotion)
        self.assertEqual(state.board.piece_at(chess.E8), chess.Piece(chess.QUEEN, chess.WHITE))

    def test_hero_check_by_knight_jump_cannot_be_blocked(self):
        """When Hero gives check via a Knight jump, it cannot be blocked by interposing a piece."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # White Hero at f6, Black King at e8 (Knight jump check: df=1, dr=2)
        # Black has pawn at e7. Interposing is impossible; Black King must move or Hero captured.
        state.board = chess.Board("4k3/4p3/5Q2/8/8/8/8/4K3 b - - 0 1")

        self.assertTrue(state.is_in_check())
        self.assertTrue(mode.is_in_check(state))

        # King legal moves
        k_moves = state.get_legal_moves_from(chess.E8)
        # e8d8, e8d7 are available
        self.assertGreater(len(k_moves), 0)

        # Pawn at e7 can capture White Hero if in reach, or push forward?
        # Pawn at e7 cannot block because Hero check is a leap!
        # Pawn at e7 can capture f6 diagonally: e7xf6!
        p_moves = state.get_legal_moves_from(chess.E7)
        p_dests = [m.to_square for m in p_moves]
        self.assertIn(chess.F6, p_dests)
        # Pawn cannot simply push e7e6 to block, because f6->e8 is a jump!
        self.assertNotIn(chess.E6, p_dests)

    def test_hero_check_by_queen_ray_can_be_blocked(self):
        """When Hero gives check via a Queen ray, a friendly piece can block the check."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # White Hero at e4, Black King at e8. Line of sight along e-file.
        # Black has a pawn at d7 that can move or another piece.
        # Let's put a Black Hero at a7.
        state.board = chess.Board("4k3/q7/8/8/4Q3/8/8/4K3 b - - 0 1")

        self.assertTrue(state.is_in_check())

        # Black Hero at a7 can block by moving to e7: a7e7!
        hero_moves = state.get_legal_moves_from(chess.A7)
        hero_dests = [m.to_square for m in hero_moves]
        self.assertIn(chess.E7, hero_dests)

    def test_checkmate_detection_in_hero_mode(self):
        """Verify checkmate detection and game-over handling in Hero Mode."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # Classic checkmate with Hero:
        # Black King in corner at h8.
        # White King at f7.
        # White Hero at g7 (protected by White King at f7, attacking h8 via Queen ray and Knight jumps).
        state.board = chess.Board("7k/5QK1/8/8/8/8/8/8 b - - 0 1")

        self.assertTrue(state.is_in_check())
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)
        self.assertIn("Checkmate", state.game_over_reason())

    def test_stalemate_detection_in_hero_mode(self):
        """Verify stalemate detection in Hero Mode."""
        mode = HeroMode()
        state = GameState(mode=mode)
        # Black King at a8 not in check.
        # White King at b6 attacks a7, b7.
        # White Hero at d7 attacks b8 via Knight jump (df=2, dr=1), but does NOT attack a8.
        # Black King at a8 has 0 legal moves, and is not in check -> Stalemate!
        state.board = chess.Board("k7/3Q4/1K6/8/8/8/8/8 b - - 0 1")

        self.assertFalse(state.is_in_check())
        self.assertTrue(state.is_game_over())
        self.assertIsNone(state.winner())
        self.assertIn("Stalemate", state.game_over_reason())

    def test_hero_piece_assets_synthesized(self):
        """Verify that Assets.get_hero_piece_asset synthesizes and caches 'wh' and 'bh'."""
        wh = Assets.get_hero_piece_asset(chess.WHITE, self.piece_images)
        bh = Assets.get_hero_piece_asset(chess.BLACK, self.piece_images)
        self.assertIn("wh", self.piece_images)
        self.assertIn("bh", self.piece_images)
        self.assertEqual(wh.get_size(), (90, 90))
        self.assertEqual(bh.get_size(), (90, 90))

    def test_renderer_mode_selector_and_panel(self):
        """Verify that renderer modal has 7 mode cards and draws Hero Mode panel without error."""
        mode = HeroMode()
        state = GameState(mode=mode)

        # Modal rects must return 7 items
        rects = self.renderer.get_mode_selector_rects()
        self.assertEqual(len(rects), 7)
        rect_hero = rects[6]
        self.assertGreater(rect_hero.width, 0)
        self.assertGreater(rect_hero.height, 0)

        # Draw modal cleanly
        self.renderer.draw_mode_selector_modal(mouse_pos=(600, 300))

        # Draw panel in Hero Mode cleanly
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

        # Draw board & pieces in Hero Mode cleanly
        self.renderer.draw_board(self.board_img)
        self.renderer.draw_pieces(state, self.piece_images)

    def test_ai_bot_selects_move_in_hero_mode(self):
        """Verify singleplayer AI bot can evaluate and select legal moves in Hero Mode."""
        mode = HeroMode()
        state = GameState(mode=mode)

        # AI Bot selects move for White on move 1
        bot_move = select_best_move(
            board=state.board,
            difficulty=BotDifficulty.CASUAL,
            game_mode=mode,
        )
        self.assertIsNotNone(bot_move)
        # Move must be legal under Hero Mode rules
        self.assertTrue(mode.is_legal_move(state.board, bot_move.from_square, bot_move.to_square))


if __name__ == "__main__":
    unittest.main()
