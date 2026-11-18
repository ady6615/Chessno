# test_crazyhouse_mode.py
"""
Unit tests for the Crazyhouse Game Mode in Chessno.
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

# Headless video driver
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import chess
import chess.variant

from game_engine import GameState, MoveResult
from crazyhouse_engine import (
    CrazyhouseMode,
    CRAZYHOUSE_PIECE_ORDER,
    PIECE_NAMES,
)
from renderer import ChessRenderer
from ai_bot import BotDifficulty, select_best_move, TRANSPOSITION_TABLE
import Assets


class TestCrazyhouseMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.screen = pygame.display.set_mode((1200, 900))
        cls.renderer = ChessRenderer(cls.screen, board_x=50, board_y=50, square_size=75)

    def setUp(self):
        TRANSPOSITION_TABLE.clear()
        self.mode = CrazyhouseMode()
        self.game_state = GameState(mode=self.mode)

    def test_crazyhouse_initialization(self):
        """Verify Crazyhouse board initializes with CrazyhouseBoard and empty pockets."""
        self.assertEqual(self.game_state.mode.name, "Crazyhouse")
        self.assertIsInstance(self.game_state.board, chess.variant.CrazyhouseBoard)
        self.assertEqual(self.game_state.turn, chess.WHITE)
        self.assertEqual(len(self.game_state.board.pockets[chess.WHITE]), 0)
        self.assertEqual(len(self.game_state.board.pockets[chess.BLACK]), 0)
        self.assertEqual(self.game_state.captured_pieces["w"], [])
        self.assertEqual(self.game_state.captured_pieces["b"], [])

    def test_captures_enter_pocket_with_capturing_color(self):
        """When a player captures an opponent piece, it enters their pocket as their color."""
        # 1. e4 d5 2. exd5 (White captures Black pawn)
        res1 = self.game_state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        res2 = self.game_state.make_move(chess.D7, chess.D5)
        self.assertTrue(res2.success)
        res3 = self.game_state.make_move(chess.E4, chess.D5)
        self.assertTrue(res3.success)
        self.assertTrue(res3.is_capture)

        # White pocket should now hold 1 pawn
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.PAWN), 1)
        self.assertEqual(len(self.game_state.board.pockets[chess.BLACK]), 0)
        self.assertIn("wP", self.game_state.captured_pieces["w"])

        # 2. ... Qxd5 (Black captures White pawn)
        res4 = self.game_state.make_move(chess.D8, chess.D5)
        self.assertTrue(res4.success)
        self.assertTrue(res4.is_capture)

        # Black pocket should now hold 1 pawn
        self.assertEqual(self.game_state.board.pockets[chess.BLACK].count(chess.PAWN), 1)
        self.assertIn("bP", self.game_state.captured_pieces["b"])

    def test_drop_move_execution_and_pocket_depletion(self):
        """A player can drop a reserve piece onto a vacant square."""
        # 1. e4 d5 2. exd5 Nf6 3. drop Pawn on e4
        self.game_state.make_move(chess.E2, chess.E4)
        self.game_state.make_move(chess.D7, chess.D5)
        self.game_state.make_move(chess.E4, chess.D5)  # White gains Pawn
        self.game_state.make_move(chess.G8, chess.F6)  # Black plays Nf6

        self.assertEqual(self.game_state.turn, chess.WHITE)
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.PAWN), 1)

        # Verify e4 is vacant
        self.assertIsNone(self.game_state.board.piece_at(chess.E4))

        # Check legal drops
        legal_drops = self.mode.get_legal_drops(self.game_state, chess.PAWN)
        self.assertIn(chess.E4, legal_drops)

        # Execute drop move
        drop_res = self.game_state.make_drop_move(chess.E4, chess.PAWN)
        self.assertTrue(drop_res.success)
        self.assertTrue(drop_res.is_drop)
        self.assertEqual(drop_res.drop_piece_type, chess.PAWN)

        # Verify piece on board is a White pawn
        placed_piece = self.game_state.board.piece_at(chess.E4)
        self.assertIsNotNone(placed_piece)
        self.assertEqual(placed_piece.piece_type, chess.PAWN)
        self.assertEqual(placed_piece.color, chess.WHITE)

        # Verify White pocket is now empty
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.PAWN), 0)
        self.assertEqual(self.game_state.captured_pieces["w"], [])

    def test_pawn_drop_rank_restrictions(self):
        """Pawns cannot be dropped onto rank 1 or rank 8."""
        # Give White a pawn in pocket
        self.game_state.board.pockets[chess.WHITE].add(chess.PAWN)
        self.mode.sync_captured_pieces(self.game_state)

        legal_drops = self.mode.get_legal_drops(self.game_state, chess.PAWN)
        for sq in legal_drops:
            r = chess.square_rank(sq)
            self.assertNotIn(r, (0, 7), f"Pawn drop square {chess.square_name(sq)} on illegal rank {r+1}")

        # Attempt illegal drop on rank 1 (e1) or rank 8 (e8)
        res_r1 = self.game_state.make_drop_move(chess.C1, chess.PAWN)
        self.assertFalse(res_r1.success)

    def test_promoted_pawn_reverts_to_pawn_when_captured(self):
        """In Crazyhouse, capturing a promoted queen yields a pawn in pocket."""
        # Setup board where White promotes a pawn to Queen, then Black captures it
        fen = "7k/P7/8/8/8/8/8/K7 w - - 0 1"
        board = chess.variant.CrazyhouseBoard(fen)
        self.game_state.board = board
        self.mode.sync_captured_pieces(self.game_state)

        # Promote a8=Q
        res_promo = self.game_state.make_move(chess.A7, chess.A8, promotion=chess.QUEEN)
        self.assertTrue(res_promo.success)
        self.assertEqual(self.game_state.board.piece_at(chess.A8).piece_type, chess.QUEEN)

        # Place a black rook on b8 and let black capture the promoted queen
        self.game_state.board.set_piece_at(chess.B8, chess.Piece(chess.ROOK, chess.BLACK))
        self.game_state.board.turn = chess.BLACK

        res_cap = self.game_state.make_move(chess.B8, chess.A8)
        self.assertTrue(res_cap.success)
        self.assertTrue(res_cap.is_capture)

        # Black pocket should have a Pawn (reverted), NOT a Queen
        self.assertEqual(self.game_state.board.pockets[chess.BLACK].count(chess.PAWN), 1)
        self.assertEqual(self.game_state.board.pockets[chess.BLACK].count(chess.QUEEN), 0)

    def test_drop_move_can_deliver_check_and_checkmate(self):
        """Dropping a piece can deliver check or checkmate."""
        # Fool's mate setup with drop:
        # FEN with White King trapped, Black drops Queen to deliver mate
        fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 3"
        board = chess.variant.CrazyhouseBoard("rnbqkbnr/pppp1ppp/8/4p3/5PP1/8/PPPPP2P/RNBQKBNR b KQkq - 0 2")
        board.pockets[chess.BLACK].add(chess.QUEEN)
        self.game_state.board = board
        self.mode.sync_captured_pieces(self.game_state)

        # Black drops Queen on h4: Q@h4#
        res = self.game_state.make_drop_move(chess.H4, chess.QUEEN)
        self.assertTrue(res.success)
        self.assertTrue(res.is_check)
        self.assertTrue(res.is_checkmate)
        self.assertEqual(self.game_state.winner(), chess.BLACK)

    def test_undo_drop_move(self):
        """Undoing a drop move returns the piece back to the player's pocket."""
        self.game_state.board.pockets[chess.WHITE].add(chess.KNIGHT)
        self.mode.sync_captured_pieces(self.game_state)
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.KNIGHT), 1)

        # Drop Knight on f3
        res = self.game_state.make_drop_move(chess.F3, chess.KNIGHT)
        self.assertTrue(res.success)
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.KNIGHT), 0)
        self.assertEqual(self.game_state.board.piece_at(chess.F3), chess.Piece(chess.KNIGHT, chess.WHITE))

        # Undo drop
        undone = self.game_state.undo_move()
        self.assertIsNotNone(undone)
        self.assertTrue(undone.is_drop)
        self.assertIsNone(self.game_state.board.piece_at(chess.F3))
        self.assertEqual(self.game_state.board.pockets[chess.WHITE].count(chess.KNIGHT), 1)

    def test_renderer_mode_selector_9_rects_and_crazyhouse_card(self):
        """Renderer get_mode_selector_rects returns 9 cards and rect[8] is Crazyhouse."""
        rects = self.renderer.get_mode_selector_rects()
        self.assertEqual(len(rects), 9)
        rect_ch = rects[8]
        self.assertGreater(rect_ch.width, 0)
        self.assertGreater(rect_ch.height, 0)

    def test_renderer_crazyhouse_reserve_rects_and_draw_panel(self):
        """Renderer draws Crazyhouse HUD and returns 5 reserve slot rects."""
        reserve_rects = self.renderer.get_crazyhouse_reserve_rects(self.game_state)
        self.assertEqual(len(reserve_rects), 5)
        for pt in CRAZYHOUSE_PIECE_ORDER:
            self.assertIn(pt, reserve_rects)
            self.assertGreater(reserve_rects[pt].width, 0)
            self.assertGreater(reserve_rects[pt].height, 0)

        # Draw panel with piece selection and pocket counts
        self.game_state.board.pockets[chess.WHITE].add(chess.KNIGHT)
        self.game_state.board.pockets[chess.BLACK].add(chess.PAWN)
        self.mode.selected_drop_piece = chess.KNIGHT
        self.mode.sync_captured_pieces(self.game_state)

        # Render panel
        self.renderer.draw_panel(
            game_state=self.game_state,
            mouse_pos=(1000, 600),
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            sound_enabled=True,
            flipped=False,
            piece_images=None,
        )

        # Draw modal
        self.renderer.draw_mode_selector_modal(
            mouse_pos=(600, 450),
            bot_controller=None,
        )

    def test_crazyhouse_reserve_piece_asset_codes_match_loaded_images(self):
        """Verify all 5 Crazyhouse pieces resolve to valid piece codes in piece_images."""
        from coordinates import piece_to_code
        _, piece_images = Assets.load_assets("Default")
        for color in [chess.WHITE, chess.BLACK]:
            for pt in CRAZYHOUSE_PIECE_ORDER:
                code = piece_to_code(chess.Piece(pt, color))
                self.assertIsNotNone(code)
                self.assertIn(code, piece_images, f"Piece code '{code}' must exist in piece_images")

    def test_crazyhouse_reserve_slots_render_with_captured_assets(self):
        """Verify reserve slots render piece images when pockets contain captured pieces."""
        _, piece_images = Assets.load_assets("Default")
        # Add captured pieces for both sides
        self.game_state.board.pockets[chess.WHITE].add(chess.PAWN)
        self.game_state.board.pockets[chess.WHITE].add(chess.QUEEN)
        self.game_state.board.pockets[chess.BLACK].add(chess.ROOK)
        self.game_state.board.pockets[chess.BLACK].add(chess.KNIGHT)
        self.game_state.board.pockets[chess.BLACK].add(chess.BISHOP)

        # White turn rendering
        self.game_state.board.turn = chess.WHITE
        self.renderer.draw_panel(
            game_state=self.game_state,
            mouse_pos=(1000, 600),
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            sound_enabled=True,
            flipped=False,
            piece_images=piece_images,
        )

        # Black turn rendering
        self.game_state.board.turn = chess.BLACK
        self.renderer.draw_panel(
            game_state=self.game_state,
            mouse_pos=(1000, 600),
            active_pack_name="Default",
            active_pack_index=0,
            total_packs=1,
            sound_enabled=True,
            flipped=True,
            piece_images=piece_images,
        )


if __name__ == "__main__":
    unittest.main()
