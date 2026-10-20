# uno_engine.py
"""
UNO mechanics and deck management for Chessno (Chess + UNO game mode).

Contains:
- UnoCardType: 1, 2, 3, Reverse, Skip
- UnoCardColor: Red, Blue, Green, Yellow
- UnoCard: Dataclass representing an individual card
- UnoDeck: Shuffled, auto-reshuffling configurable deck
- ChessUnoMode: Complete GameMode implementation integrating UNO cards with chess rules
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import random
import chess

from game_engine import GameMode, GameState, MoveResult


class UnoCardType(Enum):
    ONE = "1"
    TWO = "2"
    THREE = "3"
    REVERSE = "Reverse"
    SKIP = "Skip"


class UnoCardColor(Enum):
    RED = "Red"
    BLUE = "Blue"
    GREEN = "Green"
    YELLOW = "Yellow"


# RGB color mapping for visual rendering
UNO_COLOR_RGB: Dict[UnoCardColor, Tuple[int, int, int]] = {
    UnoCardColor.RED: (220, 48, 48),
    UnoCardColor.BLUE: (35, 115, 230),
    UnoCardColor.GREEN: (42, 175, 80),
    UnoCardColor.YELLOW: (235, 190, 25),
}


@dataclass
class UnoCard:
    """Represents an individual playable UNO card."""
    card_type: UnoCardType
    color: UnoCardColor

    @property
    def moves_allowed(self) -> int:
        """Number of legal chess moves granted by this card."""
        if self.card_type == UnoCardType.ONE:
            return 1
        elif self.card_type == UnoCardType.TWO:
            return 2
        elif self.card_type == UnoCardType.THREE:
            return 3
        elif self.card_type == UnoCardType.REVERSE:
            return 1
        elif self.card_type == UnoCardType.SKIP:
            return 1
        return 1

    @property
    def symbol(self) -> str:
        if self.card_type == UnoCardType.ONE:
            return "1"
        elif self.card_type == UnoCardType.TWO:
            return "2"
        elif self.card_type == UnoCardType.THREE:
            return "3"
        elif self.card_type == UnoCardType.REVERSE:
            return "REV"
        elif self.card_type == UnoCardType.SKIP:
            return "SKIP"
        return "?"

    @property
    def title(self) -> str:
        return f"{self.card_type.value}"

    @property
    def description(self) -> str:
        if self.card_type == UnoCardType.ONE:
            return "1 Legal Move"
        elif self.card_type == UnoCardType.TWO:
            return "2 Consecutive Moves!"
        elif self.card_type == UnoCardType.THREE:
            return "3 Consecutive Moves!"
        elif self.card_type == UnoCardType.REVERSE:
            return "Flips Board 180° + 1 Move"
        elif self.card_type == UnoCardType.SKIP:
            return "Skips Opponent Turn + 1 Move"
        return ""


class UnoDeck:
    """
    Shuffled deck of UNO cards with automatic discard reshuffling.
    Never allows the draw pile to become permanently exhausted.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self.draw_pile: List[UnoCard] = []
        self.discard_pile: List[UnoCard] = []
        self.reset()

    def reset(self) -> None:
        """Create a fresh shuffled deck."""
        self.draw_pile.clear()
        self.discard_pile.clear()
        cards = []
        # Standard composition across all 4 colors:
        # 1: 2 copies per color (8)
        # 2: 2 copies per color (8)
        # 3: 1 copy per color (4)
        # Reverse: 1 copy per color (4)
        # Skip: 1 copy per color (4)
        # Total = 28 cards
        for color in UnoCardColor:
            for _ in range(2):
                cards.append(UnoCard(UnoCardType.ONE, color))
                cards.append(UnoCard(UnoCardType.TWO, color))
            cards.append(UnoCard(UnoCardType.THREE, color))
            cards.append(UnoCard(UnoCardType.REVERSE, color))
            cards.append(UnoCard(UnoCardType.SKIP, color))

        self._rng.shuffle(cards)
        self.draw_pile = cards

    def draw(self) -> UnoCard:
        """
        Draw one card from the draw pile.
        If empty, reshuffles discard pile into draw pile.
        """
        if not self.draw_pile:
            if self.discard_pile:
                self.draw_pile = self.discard_pile[:]
                self.discard_pile.clear()
                self._rng.shuffle(self.draw_pile)
            else:
                # Discard is also empty, re-create fresh deck
                self.reset()

        card = self.draw_pile.pop()
        return card

    def discard(self, card: UnoCard) -> None:
        """Place a card into the discard pile."""
        self.discard_pile.append(card)

    @property
    def draw_pile_count(self) -> int:
        return len(self.draw_pile)

    @property
    def discard_pile_count(self) -> int:
        return len(self.discard_pile)


class ChessUnoMode(GameMode):
    """
    Chess + UNO Game Mode.

    Rules & Turn Flow:
    1. At the start of each non-skipped turn, the active player draws an UNO card.
    2. Card effects apply immediately:
       - 1, 2, 3: Grants exactly 1, 2, or 3 legal chess moves to the active player.
       - Reverse: Rotates the board display 180 degrees (toggles flipped) + grants 1 move.
       - Skip: Grants 1 move, then queues a skip for the opponent's next turn.
    3. Multi-move turns:
       - Every move must be fully legal under chess rules.
       - A move that leaves the active player's own king in check is forbidden.
       - The active player remains active until their move allowance is exhausted or 0 legal moves remain.
       - King capture is forbidden; opponents are not prematurely declared checkmated during sub-moves.
    4. Skip handling & Conflict Resolution:
       - If the player delivers checkmate with their move, the game ends immediately.
       - If the player's move leaves the opponent's king in check, the opponent's mandatory response to
         check takes precedence: the Skip is neutralized so the opponent can defend their king.
       - Consecutive Skips are tracked per-player via `skips_queued`.
       - Skipped turns do not draw an UNO card and do not count as a chess move.
    """

    def __init__(self, seed: Optional[int] = None):
        super().__init__(name="Chess + UNO")
        self.deck = UnoDeck(seed=seed)
        self.current_card: Optional[UnoCard] = None
        self.active_turn_color: chess.Color = chess.WHITE
        self.moves_allowed: int = 1
        self.moves_completed: int = 0
        self.skips_queued: Dict[chess.Color, int] = {chess.WHITE: 0, chess.BLACK: 0}
        self.board_reversed: bool = False
        self.status_message: str = "Chess + UNO initialized"
        self.skip_alert_message: Optional[str] = None

    def on_init(self, game_state: GameState) -> None:
        """Reset UNO mode state and draw the first card for White."""
        self.deck.reset()
        self.current_card = None
        self.active_turn_color = chess.WHITE
        self.moves_allowed = 1
        self.moves_completed = 0
        self.skips_queued = {chess.WHITE: 0, chess.BLACK: 0}
        self.board_reversed = False
        self.skip_alert_message = None
        self.start_turn(game_state)

    @property
    def pending_skips(self) -> int:
        return self.skips_queued[chess.WHITE] + self.skips_queued[chess.BLACK]

    @pending_skips.setter
    def pending_skips(self, val: int) -> None:
        # Default target for manual tests: the opponent of the active player
        opp = chess.BLACK if self.active_turn_color == chess.WHITE else chess.WHITE
        self.skips_queued[opp] = val

    @property
    def moves_remaining(self) -> int:
        return max(0, self.moves_allowed - self.moves_completed)

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """
        Verify mod-specific move constraints:
        - In chess, you cannot capture the enemy King (even during multi-move turns).
        """
        target_piece = game_state.board.piece_at(move.to_square)
        if target_piece and target_piece.piece_type == chess.KING:
            return False
        return True

    def start_turn(self, game_state: GameState) -> None:
        """
        Start a new turn for the current active player.
        Handles skips and draws an UNO card if not skipped.
        """
        if game_state.is_game_over():
            return

        current_color = game_state.turn
        self.active_turn_color = current_color
        color_name = "White" if current_color == chess.WHITE else "Black"

        # Check if THIS specific player's turn is skipped
        if self.skips_queued[current_color] > 0:
            self.skips_queued[current_color] -= 1
            self.skip_alert_message = f"{color_name}'s turn was SKIPPED by UNO!"
            self.status_message = f"{color_name} skipped!"
            # Pass turn directly to opponent without drawing card or making a move
            opponent = chess.BLACK if current_color == chess.WHITE else chess.WHITE
            game_state.board.turn = opponent
            self.active_turn_color = opponent
            self.start_turn(game_state)
            return

        # Do not erase neutralized alert immediately
        if not self.skip_alert_message or "neutralized" not in self.skip_alert_message:
            self.skip_alert_message = None

        # Draw a card for this turn
        if self.current_card is not None:
            self.deck.discard(self.current_card)

        card = self.deck.draw()
        self.current_card = card
        self.moves_allowed = card.moves_allowed
        self.moves_completed = 0

        # Apply immediate card effects
        if card.card_type == UnoCardType.REVERSE:
            self.board_reversed = not self.board_reversed
            self.status_message = f"{color_name} drew Reverse! Board rotated."
        elif card.card_type == UnoCardType.SKIP:
            opponent = chess.BLACK if current_color == chess.WHITE else chess.WHITE
            self.skips_queued[opponent] += 1
            self.status_message = f"{color_name} drew Skip! Opponent will be skipped."
        elif card.card_type in (UnoCardType.TWO, UnoCardType.THREE):
            self.status_message = f"{color_name} drew {card.symbol}! {card.moves_allowed} consecutive moves."
        else:
            self.status_message = f"{color_name} drew {card.symbol} ({card.color.value})."

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """
        Called immediately after a move is committed to the board.
        Handles multi-move continuation and turn termination.
        """
        self.moves_completed += 1
        active_color = self.active_turn_color
        opponent_color = chess.BLACK if active_color == chess.WHITE else chess.WHITE

        # Check if the move delivered checkmate to opponent
        game_state.board.turn = opponent_color
        if game_state.board.is_checkmate():
            # Checkmate immediately ends the game!
            self.moves_allowed = self.moves_completed
            self.skips_queued = {chess.WHITE: 0, chess.BLACK: 0}
            return

        # Restore turn to active player if they still have moves remaining
        if self.moves_remaining > 0:
            # Check if active player has any legal moves available
            game_state.board.turn = active_color
            has_legal_moves = any(game_state.get_legal_moves_from(sq) for sq in chess.SQUARES)
            if not has_legal_moves:
                # No legal moves remain: end turn early
                self.moves_allowed = self.moves_completed
                game_state.board.turn = opponent_color
            else:
                # Active player continues!
                game_state.board.turn = active_color
                return

        # At this point, the active player's turn is officially COMPLETE.
        # Set turn to opponent
        game_state.board.turn = opponent_color

        # Conflict Resolution: Check vs Skip
        # "Do not allow a Skip card to silently bypass a required response to check or override an already completed checkmate."
        if game_state.board.is_check() and self.skips_queued[opponent_color] > 0:
            # Opponent is in check! Opponent must have the opportunity to answer check.
            self.skips_queued[opponent_color] = 0
            self.skip_alert_message = "Skip neutralized: Opponent must answer check!"

        # Start next turn for the opponent
        self.start_turn(game_state)

    def on_turn_change(self, game_state: GameState) -> None:
        pass
