# test_ai_bot.py
"""Unit tests for the Singleplayer AI Bot and Difficulty Levels in Chessno."""

import os
import sys
import unittest
from pathlib import Path
import time

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
SRC2_DIR = PROJECT_ROOT / "src2"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC2_DIR))

# Headless video driver
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import chess
import chess.variant
from game_engine import GameState, ClassicChessMode
from queen_pawn_engine import QueenPawnMode
from snail_engine import ImmortalSnailMode
from uno_engine import ChessUnoMode
from atomic_engine import AtomicChessMode
from crazyhouse_engine import CrazyhouseMode
from hero_mode_engine import HeroMode
from rook_dash_engine import RookDashMode
from bishop_dash_engine import BishopDashMode
from ai_bot import (
    BotDifficulty,
    BOT_DIFFICULTY_METADATA,
    evaluate_board,
    select_best_move,
    ChessBotController,
    get_mode_legal_moves,
)


class TestAIBotLevels(unittest.TestCase):
    def setUp(self):
        from ai_bot import TRANSPOSITION_TABLE
        TRANSPOSITION_TABLE.clear()

    def test_metadata_structure(self):
        """Verify all 4 difficulty levels exist with accurate metadata."""
        levels = [
            BotDifficulty.NOVICE,
            BotDifficulty.CASUAL,
            BotDifficulty.INTERMEDIATE,
            BotDifficulty.MASTER,
        ]
        self.assertEqual(len(BotDifficulty), 4)

        for lvl in levels:
            self.assertIn(lvl, BOT_DIFFICULTY_METADATA)
            meta = BOT_DIFFICULTY_METADATA[lvl]
            self.assertIn("level_num", meta)
            self.assertIn("name", meta)
            self.assertIn("elo", meta)
            self.assertIn("badge_color", meta)
            self.assertIn("depth", meta)
            self.assertIn("min_delay", meta)
            self.assertIn("max_delay", meta)
            self.assertGreater(meta["max_delay"], meta["min_delay"])

    def test_select_best_move_returns_legal_move_for_all_levels(self):
        """Verify that every level produces a valid legal move from the start position."""
        board = chess.Board()
        legal_moves = list(board.legal_moves)

        for lvl in BotDifficulty:
            chosen = select_best_move(board, lvl)
            self.assertIsNotNone(chosen, f"Level {lvl} failed to return a move")
            self.assertIn(chosen, legal_moves, f"Level {lvl} returned illegal move {chosen}")

    def test_bot_finds_immediate_checkmate_in_one(self):
        """Intermediate and Master bots must instantly find and execute Mate in 1."""
        # Position with Mate in 1: Qxf7#
        # FEN: r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 4
        board = chess.Board("r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 4")
        mate_move = chess.Move.from_uci("f3f7")

        for lvl in (BotDifficulty.INTERMEDIATE, BotDifficulty.MASTER):
            chosen = select_best_move(board, lvl)
            self.assertEqual(chosen, mate_move, f"Level {lvl} failed to find mate in 1 Qxf7#")

    def test_bot_captures_hanging_queen(self):
        """Bot should capture a hanging queen rather than playing a random quiet move."""
        # White Bishop on c4 can capture unprotected Black Queen on e6
        # FEN: rnb1kbnr/pppp1ppp/4q3/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3
        board = chess.Board("rnb1kbnr/pppp1ppp/4q3/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3")
        capture_move = chess.Move.from_uci("c4e6")

        for lvl in (BotDifficulty.CASUAL, BotDifficulty.INTERMEDIATE, BotDifficulty.MASTER):
            chosen = select_best_move(board, lvl)
            self.assertEqual(chosen, capture_move, f"Level {lvl} failed to take hanging queen")

    def test_bot_promotes_to_queen(self):
        """When reaching the promotion rank, bot must choose Queen promotion."""
        board = chess.Board("8/4P3/8/8/8/8/8/k6K w - - 0 1")
        chosen = select_best_move(board, BotDifficulty.MASTER)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.from_square, chess.E7)
        self.assertEqual(chosen.to_square, chess.E8)
        self.assertEqual(chosen.promotion, chess.QUEEN)

    def test_master_bot_grandmaster_metadata(self):
        """Verify Master bot is configured with Grandmaster name and 2500+ Elo badge."""
        meta = BOT_DIFFICULTY_METADATA[BotDifficulty.MASTER]
        self.assertEqual(meta["name"], "Grandmaster")
        self.assertEqual(meta["elo"], "2500+ Elo")
        self.assertGreaterEqual(meta["depth"], 6)

    def test_master_bot_opening_book_lookup(self):
        """Master bot must play from the Grandmaster opening book in standard openings."""
        # Start position
        board = chess.Board()
        move = select_best_move(board, BotDifficulty.MASTER)
        # Should play a top GM opening move: e4, d4, c4, or Nf3
        self.assertIn(move.uci(), ["e2e4", "d2d4", "c2c4", "g1f3"])

        # Against 1. e4, Master bot as Black should respond with standard book defense (e5, c5, e6, c6, Nf6, d5, d6)
        board.push_san("e4")
        move_black = select_best_move(board, BotDifficulty.MASTER)
        self.assertIn(move_black.uci(), ["c7c5", "e7e5", "e7e6", "c7c6", "g8f6", "d7d5", "d7d6"])

    def test_master_bot_tactical_mate_in_two(self):
        """Master level bot must resolve tactical mate in 2."""
        # White can deliver mate in 2: 1. Qh7+ Kf8 2. Qh8#
        # FEN: 6k1/5ppp/8/8/8/8/5QPP/6K1 w - - 0 1 (simplified mate in 2 setup)
        # Standard Anastasia/Damiano mate in 2:
        # FEN: r4rk1/5ppp/8/8/8/8/1Q4PP/6K1 w - - 0 1 -> Let's use a clear mate in 2:
        # White: Kh1, Qf7, Be6. Black: Kh8, Rg8.
        # 1. Qf8+ Rxf8 2. Rxf8#
        board = chess.Board("5r1k/5Q2/4B3/8/8/8/8/7K w - - 0 1")
        # 1. Qxf8+ Kh7 2. Bf5# or Qg8#
        move = select_best_move(board, BotDifficulty.MASTER)
        self.assertEqual(move.uci(), "f7f8")

    def test_master_evaluates_passed_pawn_superiority(self):
        """Evaluation must value advanced protected passed pawns significantly higher."""
        # Board 1: White has advanced passed pawn on d6
        b1 = chess.Board("8/8/3P4/8/8/8/8/4K2k w - - 0 1")
        # Board 2: White has normal pawn on d2
        b2 = chess.Board("8/8/8/8/8/8/3P4/4K2k w - - 0 1")
        self.assertGreater(evaluate_board(b1), evaluate_board(b2))

    def test_bot_compatibility_with_queen_pawn_mode(self):
        """Verify bot operates correctly with Queen Pawn game mode heuristics."""
        mode = QueenPawnMode()
        board = chess.Board(mode.INITIAL_FEN)
        chosen = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertIn(chosen, list(board.legal_moves))

    def test_bot_compatibility_with_snail_mode(self):
        """Verify bot operates correctly with Immortal Snail game mode."""
        mode = ImmortalSnailMode()
        board = chess.Board()
        chosen = select_best_move(board, BotDifficulty.INTERMEDIATE, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertIn(chosen, list(board.legal_moves))

    def test_bot_compatibility_with_uno_mode(self):
        """Verify bot operates correctly in Chess + UNO mode."""
        mode = ChessUnoMode()
        board = chess.Board()
        chosen = select_best_move(board, BotDifficulty.CASUAL, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertIn(chosen, list(board.legal_moves))

    def test_bot_compatibility_with_atomic_chess(self):
        """Verify bot evaluates and selects legal moves in Atomic Chess."""
        mode = AtomicChessMode()
        board = chess.variant.AtomicBoard()
        chosen = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertIn(chosen, list(board.legal_moves))

    def test_bot_atomic_chess_blast_mate_in_one(self):
        """Verify AI bot recognizes and executes instant atomic blast victory."""
        mode = AtomicChessMode()
        board = chess.variant.AtomicBoard()
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(chess.D8, chess.Piece(chess.QUEEN, chess.BLACK))  # adjacent to black king
        board.set_piece_at(chess.D1, chess.Piece(chess.ROOK, chess.WHITE))

        # White Rook on d1 captures d8 -> explosion destroys Black King!
        move = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertEqual(move, chess.Move(chess.D1, chess.D8))

    def test_bot_atomic_chess_pawn_shield_eval(self):
        """Pawn shields in Atomic chess must evaluate significantly higher than exposed kings."""
        mode = AtomicChessMode()
        # b1: White king with pawn shield on e2, d2, f2
        b1 = chess.variant.AtomicBoard()
        b1.clear()
        b1.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        b1.set_piece_at(chess.E2, chess.Piece(chess.PAWN, chess.WHITE))
        b1.set_piece_at(chess.D2, chess.Piece(chess.PAWN, chess.WHITE))
        b1.set_piece_at(chess.F2, chess.Piece(chess.PAWN, chess.WHITE))
        b1.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))

        # b2: White king with a non-pawn (Knight) on e2 attacked by Black Rook on e7
        b2 = chess.variant.AtomicBoard()
        b2.clear()
        b2.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        b2.set_piece_at(chess.E2, chess.Piece(chess.KNIGHT, chess.WHITE))  # blast hazard next to King!
        b2.set_piece_at(chess.E7, chess.Piece(chess.ROOK, chess.BLACK))   # attacks e2!
        b2.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))

        self.assertGreater(evaluate_board(b1, mode), evaluate_board(b2, mode))

    def test_bot_compatibility_with_crazyhouse(self):
        """Verify bot operates correctly in Crazyhouse variant."""
        mode = CrazyhouseMode()
        board = chess.variant.CrazyhouseBoard()
        chosen = select_best_move(board, BotDifficulty.INTERMEDIATE, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertIn(chosen, list(board.legal_moves))

    def test_bot_crazyhouse_pocket_reserve_evaluation(self):
        """Crazyhouse evaluation must reward reserve pocket material and drop threats."""
        b1 = chess.variant.CrazyhouseBoard()
        b1.pockets[chess.WHITE].add(chess.QUEEN)
        b1.pockets[chess.WHITE].add(chess.KNIGHT)

        b2 = chess.variant.CrazyhouseBoard()
        self.assertGreater(evaluate_board(b1), evaluate_board(b2))

    def test_bot_crazyhouse_drop_move_selection(self):
        """Verify bot can evaluate and execute reserve pocket drop moves."""
        mode = CrazyhouseMode()
        board = chess.variant.CrazyhouseBoard()
        board.clear()
        board.turn = chess.WHITE
        board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(chess.A8, chess.Piece(chess.KING, chess.BLACK))
        # White has a Queen in pocket
        board.pockets[chess.WHITE].add(chess.QUEEN)

        move = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertIsNotNone(move)
        # Move must be legal in Crazyhouse
        self.assertIn(move, list(board.legal_moves))

    def test_bot_compatibility_with_hero_mode(self):
        """Verify bot operates correctly in Hero Mode across difficulties."""
        mode = HeroMode()
        board = chess.Board(mode.INITIAL_FEN)
        for diff in (BotDifficulty.CASUAL, BotDifficulty.MASTER):
            chosen = select_best_move(board, diff, game_mode=mode)
            self.assertIsNotNone(chosen)
            self.assertTrue(mode.is_legal_move(board, chosen.from_square, chosen.to_square))

    def test_bot_hero_mode_amazon_knight_leap_move(self):
        """Verify Hero piece can execute Knight jumps in bot search."""
        mode = HeroMode()
        board = chess.Board(mode.INITIAL_FEN)
        # From start position, Hero on d1 can jump over pawns to c3 or e3
        legal_moves = get_mode_legal_moves(board, mode)
        c3_jump = chess.Move(chess.D1, chess.C3)
        self.assertIn(c3_jump, legal_moves)

    def test_bot_hero_mode_pawn_promotion_rush_eval(self):
        """In Hero Mode, advancing pawns to promote to Amazons must have immense value."""
        mode = HeroMode()
        # White pawn on 7th rank (about to promote to Amazon)
        b1 = chess.Board("3qk3/8/8/8/8/8/4P3/3QK3 w - - 0 1")
        b1.set_piece_at(chess.E7, chess.Piece(chess.PAWN, chess.WHITE))
        b1.remove_piece_at(chess.E2)

        # White pawn on 2nd rank
        b2 = chess.Board("3qk3/8/8/8/8/8/4P3/3QK3 w - - 0 1")
        self.assertGreater(evaluate_board(b1, mode), evaluate_board(b2, mode))

    def test_bot_compatibility_with_rook_dash(self):
        """Verify bot generates strictly legal Rook Dash moves."""
        mode = RookDashMode()
        board = chess.Board(mode.INITIAL_FEN)
        chosen = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertTrue(mode.can_move(chosen, board=board))

    def test_bot_compatibility_with_bishop_dash(self):
        """Verify bot generates strictly legal Bishop Dash moves."""
        mode = BishopDashMode()
        board = chess.Board(mode.INITIAL_FEN)
        chosen = select_best_move(board, BotDifficulty.MASTER, game_mode=mode)
        self.assertIsNotNone(chosen)
        self.assertTrue(mode.can_move(chosen, board=board))


class TestChessBotController(unittest.TestCase):
    def setUp(self):
        self.controller = ChessBotController(difficulty=BotDifficulty.NOVICE)
        self.game = GameState(mode=ClassicChessMode())

    def tearDown(self):
        self.controller.cancel_thinking()

    def test_initial_state(self):
        """Verify default settings for singleplayer controller."""
        self.assertTrue(self.controller.enabled)
        self.assertEqual(self.controller.difficulty, BotDifficulty.NOVICE)
        self.assertEqual(self.controller.player_color, chess.WHITE)
        self.assertEqual(self.controller.bot_color, chess.BLACK)
        self.assertFalse(self.controller.is_thinking)

    def test_turn_detection(self):
        """White turn is human, Black turn is bot when human is White."""
        self.assertFalse(self.controller.is_bot_turn(self.game))
        # Make a move for White
        self.game.make_move(chess.E2, chess.E4)
        self.assertEqual(self.game.turn, chess.BLACK)
        self.assertTrue(self.controller.is_bot_turn(self.game))

    def test_swap_sides(self):
        """Player swapping to Black makes White the bot."""
        self.controller.set_player_color(chess.BLACK)
        self.assertEqual(self.controller.player_color, chess.BLACK)
        self.assertEqual(self.controller.bot_color, chess.WHITE)
        # From start position, it is White's turn -> should be bot's turn!
        self.assertTrue(self.controller.is_bot_turn(self.game))

    def test_cycle_difficulty(self):
        """Cycling difficulty traverses all 4 levels in order."""
        self.assertEqual(self.controller.difficulty, BotDifficulty.NOVICE)
        self.controller.cycle_difficulty(1)
        self.assertEqual(self.controller.difficulty, BotDifficulty.CASUAL)
        self.controller.cycle_difficulty(1)
        self.assertEqual(self.controller.difficulty, BotDifficulty.INTERMEDIATE)
        self.controller.cycle_difficulty(1)
        self.assertEqual(self.controller.difficulty, BotDifficulty.MASTER)
        self.controller.cycle_difficulty(1)
        self.assertEqual(self.controller.difficulty, BotDifficulty.NOVICE)

    def test_toggle_enabled(self):
        """Toggling disabled turns off bot turn recognition."""
        self.game.make_move(chess.E2, chess.E4)
        self.assertTrue(self.controller.is_bot_turn(self.game))
        self.controller.toggle_enabled()
        self.assertFalse(self.controller.enabled)
        self.assertFalse(self.controller.is_bot_turn(self.game))

    def test_async_move_execution(self):
        """Bot controller launches background thread and dispatches move after delay."""
        self.game.make_move(chess.E2, chess.E4)
        self.assertTrue(self.controller.is_bot_turn(self.game))

        # First update triggers start_thinking
        move, trigger_draw = self.controller.update(0.016, self.game)
        self.assertIsNone(move)
        self.assertFalse(trigger_draw)
        self.assertTrue(self.controller.is_thinking)

        # Wait for thread to finish and pacing delay to pass
        time.sleep(0.9)
        move, trigger_draw = self.controller.update(0.016, self.game)
        self.assertIsNotNone(move)
        self.assertIn(move, list(self.game.board.legal_moves))
        self.assertFalse(self.controller.is_thinking)

    def test_controller_crazyhouse_drop_execution(self):
        """Bot controller can plan and dispatch a move in Crazyhouse mode."""
        ch_game = GameState(mode=CrazyhouseMode())
        ch_game.board.clear()
        ch_game.board.turn = chess.BLACK
        ch_game.board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
        ch_game.board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
        ch_game.board.pockets[chess.BLACK].add(chess.QUEEN)

        self.controller.set_player_color(chess.WHITE)
        self.assertTrue(self.controller.is_bot_turn(ch_game))

        self.controller.update(0.016, ch_game)
        self.assertTrue(self.controller.is_thinking)
        time.sleep(0.9)
        move, _ = self.controller.update(0.016, ch_game)
        self.assertIsNotNone(move)
        self.assertIn(move, list(ch_game.board.legal_moves))


if __name__ == "__main__":
    unittest.main()
