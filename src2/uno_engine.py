# uno_engine.py
"""
UNO mechanics and deck management for Chessno (Chess + UNO game mode).

Contains:
- UnoCardType: 1, 2, 3, Reverse, Skip
- UnoCardColor: Red, Blue, Green, Yellow
- UnoTurnPhase: AWAITING_DRAW, SHUFFLING, CARD_ACTIVE
- UnoCard: Dataclass representing an individual card
- UnoDeck: Shuffled, auto-reshuffling configurable deck
- ChessUnoMode: Complete GameMode implementation with button-triggered draw and shuffle animation
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


class UnoTurnPhase(Enum):
    AWAITING_DRAW = "Awaiting Draw"   # Waiting for player to press "Draw Card"
    SHUFFLING = "Shuffling"           # Card shuffle animation in progress
    CARD_ACTIVE = "Card Active"       # Card revealed, player makes legal chess move(s)


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
                self.reset()

        return self.draw_pile.pop()

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
    Chess + UNO Game Mode with interactive button draw and shuffle animation.

    Turn Flow:
    1. At the start of a turn, the mode enters AWAITING_DRAW phase.
    2. The player presses the 'Draw Card' button or [Space].
    3. The mode enters SHUFFLING phase: cards shuffle visually for ~0.6s with audio.
    4. The card is revealed, enters CARD_ACTIVE phase, and its effects apply immediately.
    5. The player completes their allocated chess moves.
    """

    def __init__(self, seed: Optional[int] = None, auto_draw: bool = False):
        super().__init__(name="Chess + UNO")
        self.deck = UnoDeck(seed=seed)
        self.auto_draw = auto_draw
        self._current_card: Optional[UnoCard] = None
        self.pending_draw_card: Optional[UnoCard] = None
        self.phase: UnoTurnPhase = UnoTurnPhase.AWAITING_DRAW
        self.active_turn_color: chess.Color = chess.WHITE
        self.moves_allowed: int = 1
        self.moves_completed: int = 0
        self.skips_queued: Dict[chess.Color, int] = {chess.WHITE: 0, chess.BLACK: 0}
        self.board_reversed: bool = False
        self.status_message: str = "Chess + UNO initialized"
        self.skip_alert_message: Optional[str] = None

        # Shuffle animation parameters
        self.shuffle_frames_remaining: int = 0
        self.shuffle_total_frames: int = 36
        self.shuffle_progress: float = 0.0

    @property
    def current_card(self) -> Optional[UnoCard]:
        return self._current_card

    @current_card.setter
    def current_card(self, card: Optional[UnoCard]) -> None:
        self._current_card = card
        if card is not None:
            self.phase = UnoTurnPhase.CARD_ACTIVE

    def on_init(self, game_state: GameState) -> None:
        """Reset UNO mode state and prepare initial turn for White."""
        self.deck.reset()
        self._current_card = None
        self.pending_draw_card = None
        self.phase = UnoTurnPhase.AWAITING_DRAW
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
        opp = chess.BLACK if self.active_turn_color == chess.WHITE else chess.WHITE
        self.skips_queued[opp] = val

    @property
    def moves_remaining(self) -> int:
        return max(0, self.moves_allowed - self.moves_completed)

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """
        Verify mod-specific move constraints:
        - Pieces cannot be moved until a card has been drawn and revealed.
        - Capturing the enemy King is forbidden.
        """
        if self.phase != UnoTurnPhase.CARD_ACTIVE:
            return False

        target_piece = game_state.board.piece_at(move.to_square)
        if target_piece and target_piece.piece_type == chess.KING:
            return False
        return True

    def start_turn(self, game_state: GameState) -> None:
        """
        Initialize the turn for the active player.
        Checks for pending skips, and if not skipped, waits for player to draw.
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
            opponent = chess.BLACK if current_color == chess.WHITE else chess.WHITE
            game_state.board.turn = opponent
            self.active_turn_color = opponent
            self.start_turn(game_state)
            return

        if not self.skip_alert_message or "neutralized" not in self.skip_alert_message:
            self.skip_alert_message = None

        if self.auto_draw:
            self.trigger_draw(game_state, animate=False)
        else:
            self.phase = UnoTurnPhase.AWAITING_DRAW
            self._current_card = None
            self.pending_draw_card = None
            self.moves_allowed = 0
            self.moves_completed = 0
            self.status_message = f"{color_name}: Press 'Draw Card' to draw your UNO card!"

    def trigger_draw(self, game_state: GameState, animate: bool = True) -> None:
        """
        Triggered when the player presses the 'Draw Card' button or [Space].
        Starts the shuffle animation or reveals immediately if animate is False.
        """
        if self.phase != UnoTurnPhase.AWAITING_DRAW and not self.auto_draw:
            return

        if self._current_card is not None:
            self.deck.discard(self._current_card)

        card = self.deck.draw()
        color_name = "White" if self.active_turn_color == chess.WHITE else "Black"

        if animate:
            self.pending_draw_card = card
            self.phase = UnoTurnPhase.SHUFFLING
            self.shuffle_total_frames = 36  # ~0.60 seconds at 60 FPS
            self.shuffle_frames_remaining = self.shuffle_total_frames
            self.shuffle_progress = 0.0
            self.status_message = f"{color_name} is shuffling cards..."
            try:
                import Assets
                Assets.play_sound("card_shuffle")
            except Exception:
                pass
        else:
            self.apply_drawn_card(game_state, card)

    def apply_drawn_card(self, game_state: GameState, card: UnoCard) -> None:
        """Commit the drawn card into the active game state."""
        self._current_card = card
        self.pending_draw_card = None
        self.phase = UnoTurnPhase.CARD_ACTIVE
        self.moves_allowed = card.moves_allowed
        self.moves_completed = 0
        color_name = "White" if self.active_turn_color == chess.WHITE else "Black"

        if card.card_type == UnoCardType.REVERSE:
            self.board_reversed = not self.board_reversed
            self.status_message = f"{color_name} drew Reverse! Board rotated."
        elif card.card_type == UnoCardType.SKIP:
            opponent = chess.BLACK if self.active_turn_color == chess.WHITE else chess.WHITE
            self.skips_queued[opponent] += 1
            self.status_message = f"{color_name} drew Skip! Opponent will be skipped."
        elif card.card_type in (UnoCardType.TWO, UnoCardType.THREE):
            self.status_message = f"{color_name} drew {card.symbol}! {card.moves_allowed} consecutive moves."
        else:
            self.status_message = f"{color_name} drew {card.symbol} ({card.color.value})."

        try:
            import Assets
            Assets.play_sound("card_flip")
        except Exception:
            pass

    def update_shuffle(self, game_state: GameState) -> None:
        """Update animation frame during the SHUFFLING phase."""
        if self.phase != UnoTurnPhase.SHUFFLING:
            return

        self.shuffle_frames_remaining -= 1
        elapsed = self.shuffle_total_frames - self.shuffle_frames_remaining
        self.shuffle_progress = min(1.0, elapsed / self.shuffle_total_frames)

        if self.shuffle_frames_remaining <= 0:
            if self.pending_draw_card:
                self.apply_drawn_card(game_state, self.pending_draw_card)

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
            self.moves_allowed = self.moves_completed
            self.skips_queued = {chess.WHITE: 0, chess.BLACK: 0}
            return

        # Restore turn to active player if they still have moves remaining
        if self.moves_remaining > 0:
            game_state.board.turn = active_color
            has_legal_moves = any(game_state.get_legal_moves_from(sq) for sq in chess.SQUARES)
            if not has_legal_moves:
                self.moves_allowed = self.moves_completed
                game_state.board.turn = opponent_color
            else:
                game_state.board.turn = active_color
                return

        # Active player's turn is officially COMPLETE
        game_state.board.turn = opponent_color

        # Conflict Resolution: Check vs Skip
        if game_state.board.is_check() and self.skips_queued[opponent_color] > 0:
            self.skips_queued[opponent_color] = 0
            self.skip_alert_message = "Skip neutralized: Opponent must answer check!"

        # Start next turn for the opponent
        self.start_turn(game_state)

    def on_turn_change(self, game_state: GameState) -> None:
        pass
