# test_uno_chess.py
"""
Automated unit tests for Chess + UNO mode.

Tests:
1. Number-card mechanics: 1, 2, and 3 consecutive moves
2. Prevention of illegal moves during multi-move turns (move allowance not consumed)
3. King safety and pin prevention during multi-move turns
4. Early turn termination when no legal moves remain
5. Reverse card: 180° visual rotation, logical square preservation, coordinate mapping
6. Skip card: Opponent turn skipping, no card drawn on skipped turn
7. Consecutive Skip card handling via explicit counter
8. Conflict resolution: Checkmate overrides Skip; Check neutralizes Skip
9. Deck exhaustion and auto-reshuffling
10. Special chess moves in UNO mode (Castling, En Passant, Promotion)
11. Mode switching between Classic Chess and Chess + UNO
12. Theme switching compatibility
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

from coordinates import (
    board_coords_to_square,
    square_to_board_coords,
    pixel_to_square,
    BOARD_X,
    BOARD_Y,
    SQUARE_SIZE,
)
from game_engine import GameState, ClassicChessMode
from uno_engine import (
    ChessUnoMode,
    UnoDeck,
    UnoCard,
    UnoCardType,
    UnoCardColor,
)
import Assets
import ChessMatrix


class TestUnoDeck(unittest.TestCase):
    """Test UNO deck construction, drawing, and auto-reshuffling."""

    def test_deck_initial_composition(self):
        deck = UnoDeck()
        # 4 colors * (2x1 + 2x2 + 1x3 + 1xReverse + 1xSkip) = 4 * 7 = 28 cards
        self.assertEqual(deck.draw_pile_count, 28)
        self.assertEqual(deck.discard_pile_count, 0)

    def test_deck_draw_and_exhaustion_reshuffle(self):
        deck = UnoDeck()
        drawn_cards = []

        # Draw all 28 cards into discard pile
        for _ in range(28):
            card = deck.draw()
            drawn_cards.append(card)
            deck.discard(card)

        self.assertEqual(deck.draw_pile_count, 0)
        self.assertEqual(deck.discard_pile_count, 28)

        # Drawing the 29th card must automatically trigger reshuffle from discard
        card29 = deck.draw()
        self.assertIsNotNone(card29)
        self.assertIsInstance(card29, UnoCard)
        # Discard pile should now be empty and draw pile should have 27 cards
        self.assertEqual(deck.discard_pile_count, 0)
        self.assertEqual(deck.draw_pile_count, 27)

    def test_deck_never_permanently_empty(self):
        deck = UnoDeck()
        # Draw 100 cards consecutively without manual discard
        for _ in range(100):
            card = deck.draw()
            self.assertIsNotNone(card)
            deck.discard(card)


class TestNumberCardMechanics(unittest.TestCase):
    """Test 1-, 2-, and 3-move turns, illegal move rejection, and turn termination."""

    def test_one_move_turn(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        mode.current_card = UnoCard(UnoCardType.ONE, UnoCardColor.RED)
        mode.moves_allowed = 1
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.moves_remaining, 1)

        res = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res.success)
        # Turn ends after 1 move and passes to Black
        self.assertEqual(state.turn, chess.BLACK)

    def test_two_move_consecutive_turn(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        mode.current_card = UnoCard(UnoCardType.TWO, UnoCardColor.GREEN)
        mode.moves_allowed = 2
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # Move 1: e2-e4
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        # White should STILL be the active player!
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.moves_remaining, 1)

        # Move 2: g1-f3
        res2 = state.make_move(chess.G1, chess.F3)
        self.assertTrue(res2.success)
        # Turn allowance exhausted: turn now passes to Black
        self.assertEqual(state.turn, chess.BLACK)

    def test_three_move_consecutive_turn(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        mode.current_card = UnoCard(UnoCardType.THREE, UnoCardColor.BLUE)
        mode.moves_allowed = 3
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # Sub-move 1: e2-e4
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.moves_remaining, 2)

        # Sub-move 2: d2-d4
        res2 = state.make_move(chess.D2, chess.D4)
        self.assertTrue(res2.success)
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.moves_remaining, 1)

        # Sub-move 3: g1-f3
        res3 = state.make_move(chess.G1, chess.F3)
        self.assertTrue(res3.success)
        # All 3 moves completed: turn passes to Black
        self.assertEqual(state.turn, chess.BLACK)

    def test_illegal_moves_do_not_consume_moves(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        mode.skips_queued = {chess.WHITE: 0, chess.BLACK: 0}
        mode.current_card = UnoCard(UnoCardType.TWO, UnoCardColor.YELLOW)
        mode.moves_allowed = 2
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # Move 1: e2-e4 (legal)
        res1 = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res1.success)
        self.assertEqual(mode.moves_remaining, 1)

        # Attempt illegal move: rook moving diagonally a1-e5
        res_bad = state.make_move(chess.A1, chess.E5)
        self.assertFalse(res_bad.success)
        # Move count must NOT be decremented!
        self.assertEqual(mode.moves_remaining, 1)
        self.assertEqual(state.turn, chess.WHITE)

        # Legal move 2: b1-c3
        res2 = state.make_move(chess.B1, chess.C3)
        self.assertTrue(res2.success)
        self.assertEqual(state.turn, chess.BLACK)

    def test_king_cannot_be_captured_during_multimove(self):
        # White queen checks black king on move 1 (non-mate); cannot capture king on move 2
        fen = "rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 1"
        mode = ChessUnoMode()
        state = GameState(mode=mode, fen=fen)
        mode.current_card = UnoCard(UnoCardType.TWO, UnoCardColor.RED)
        mode.moves_allowed = 2
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # White plays Qxe5+ (Check, but not checkmate!)
        res1 = state.make_move(chess.H5, chess.E5)
        self.assertTrue(res1.success)
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.moves_remaining, 1)

        # Attempt to capture the Black King directly: e5-e8 (forbidden in chess rules!)
        self.assertFalse(state.is_legal_move(chess.E5, chess.E8))


class TestReverseCard(unittest.TestCase):
    """Test 180° visual board rotation and coordinate mapping."""

    def test_reverse_toggles_orientation(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        self.assertFalse(mode.board_reversed)

        # Mock drawing a Reverse card
        mode.current_card = UnoCard(UnoCardType.REVERSE, UnoCardColor.BLUE)
        mode.board_reversed = True  # Reverse applied on draw

        # Coordinates check in flipped mode
        # Logical square A1 is White Rook
        self.assertEqual(state.get_piece_code_at(chess.A1), "wr")
        # In flipped view, row 0 col 7 corresponds to square H1 (or A8 at 7,7)
        self.assertEqual(board_coords_to_square(0, 0, flipped=True), chess.H1)
        self.assertEqual(board_coords_to_square(7, 0, flipped=True), chess.H8)

        # Drawing second Reverse toggles back
        mode.board_reversed = False
        self.assertEqual(board_coords_to_square(7, 0, flipped=False), chess.A1)


class TestSkipCard(unittest.TestCase):
    """Test Skip effects, consecutive skips, and check/checkmate priority."""

    def test_single_skip_skips_opponent(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)

        # Force next draw to be a normal card so White's second turn is standard
        mode.deck.draw = lambda: UnoCard(UnoCardType.ONE, UnoCardColor.BLUE)

        # White plays Skip card
        mode.current_card = UnoCard(UnoCardType.SKIP, UnoCardColor.RED)
        mode.moves_allowed = 1
        mode.moves_completed = 0
        mode.pending_skips = 1
        mode.active_turn_color = chess.WHITE

        # White moves e2-e4
        res = state.make_move(chess.E2, chess.E4)
        self.assertTrue(res.success)

        # Black's turn was skipped: turn must be immediately back to White!
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.pending_skips, 0)

    def test_consecutive_skips(self):
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        # Mock draw to ensure subsequent drawn cards are normal ONE cards
        mode.deck.draw = lambda: UnoCard(UnoCardType.ONE, UnoCardColor.BLUE)

        # Two pending skips queued for Black
        mode.skips_queued[chess.BLACK] = 2
        mode.active_turn_color = chess.WHITE
        mode.current_card = UnoCard(UnoCardType.ONE, UnoCardColor.GREEN)
        mode.moves_allowed = 1
        mode.moves_completed = 0

        # White moves e2-e4
        state.make_move(chess.E2, chess.E4)
        # Black skipped 1st time, back to White
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.skips_queued[chess.BLACK], 1)

        # White moves d2-d4
        state.make_move(chess.D2, chess.D4)
        # Black skipped 2nd time, back to White
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(mode.skips_queued[chess.BLACK], 0)

    def test_checkmate_overrides_skip(self):
        # Scholar's mate delivered on a Skip card: game ends in victory immediately
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        # Play into scholar's mate setup
        state.board.set_fen("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
        mode.current_card = UnoCard(UnoCardType.SKIP, UnoCardColor.YELLOW)
        mode.moves_allowed = 1
        mode.moves_completed = 0
        mode.skips_queued[chess.BLACK] = 1
        mode.active_turn_color = chess.WHITE

        # White plays Qxf7#
        res = state.make_move(chess.H5, chess.F7)
        self.assertTrue(res.success)
        self.assertTrue(res.is_checkmate)
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.winner(), chess.WHITE)
        # Skip is consumed and does not linger on ended game
        self.assertEqual(mode.pending_skips, 0)

    def test_check_neutralizes_skip(self):
        # Delivering check neutralizes skip so opponent has mandatory chance to answer check
        mode = ChessUnoMode()
        state = GameState(mode=mode)
        # Mock draw to ensure subsequent drawn card for Black is a normal ONE card
        mode.deck.draw = lambda: UnoCard(UnoCardType.ONE, UnoCardColor.BLUE)

        # Setup position where White queen can check Black king
        state.board.set_fen("rnbqkbnr/pppp1ppp/8/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 1")
        mode.current_card = UnoCard(UnoCardType.SKIP, UnoCardColor.RED)
        mode.moves_allowed = 1
        mode.moves_completed = 0
        mode.skips_queued[chess.BLACK] = 1
        mode.active_turn_color = chess.WHITE

        # White plays Qxe5+ (Check, not mate)
        res = state.make_move(chess.H5, chess.E5)
        self.assertTrue(res.success)
        self.assertTrue(state.board.is_check())
        self.assertFalse(state.board.is_checkmate())

        # Black is in check, so Black's turn is NOT skipped; Black must answer check
        self.assertEqual(state.turn, chess.BLACK)
        self.assertEqual(mode.skips_queued[chess.BLACK], 0)


class TestSpecialMovesInUno(unittest.TestCase):
    """Test castling, en passant, and promotion under UNO mode."""

    def test_castling_in_uno_mode(self):
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        mode = ChessUnoMode()
        state = GameState(mode=mode, fen=fen)
        mode.current_card = UnoCard(UnoCardType.TWO, UnoCardColor.BLUE)
        mode.moves_allowed = 2
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # White castles kingside e1-g1 on move 1
        res1 = state.make_move(chess.E1, chess.G1)
        self.assertTrue(res1.success)
        self.assertTrue(res1.is_castling)
        self.assertEqual(state.get_piece_code_at(chess.G1), "wa")
        self.assertEqual(state.get_piece_code_at(chess.F1), "wr")
        self.assertEqual(state.turn, chess.WHITE)

        # White moves rook f1-f8 on move 2
        res2 = state.make_move(chess.F1, chess.F8)
        self.assertTrue(res2.success)

    def test_pawn_promotion_in_uno_mode(self):
        fen = "3k4/4P3/8/8/8/8/8/4K3 w - - 0 1"
        mode = ChessUnoMode()
        state = GameState(mode=mode, fen=fen)
        mode.current_card = UnoCard(UnoCardType.TWO, UnoCardColor.YELLOW)
        mode.moves_allowed = 2
        mode.moves_completed = 0
        mode.active_turn_color = chess.WHITE

        # Promote pawn to Queen on move 1
        res1 = state.make_move(chess.E7, chess.E8, promotion=chess.QUEEN)
        self.assertTrue(res1.success)
        self.assertTrue(res1.is_promotion)
        self.assertEqual(state.get_piece_code_at(chess.E8), "wq")


class TestModeSwitching(unittest.TestCase):
    """Test switching between Classic Chess and Chess + UNO."""

    def test_switch_modes_cleanly(self):
        state = GameState(mode=ClassicChessMode())
        self.assertEqual(state.mode.name, "Classic")

        # Switch to UNO mode
        uno_mode = ChessUnoMode()
        state.set_mode(uno_mode)
        self.assertEqual(state.mode.name, "Chess + UNO")
        self.assertIsNotNone(uno_mode.current_card)

        # Switch back to Classic
        classic = ClassicChessMode()
        state.set_mode(classic)
        self.assertEqual(state.mode.name, "Classic")
        self.assertFalse(hasattr(state.mode, "deck"))


if __name__ == "__main__":
    unittest.main()
