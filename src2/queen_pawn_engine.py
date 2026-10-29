# queen_pawn_engine.py
"""
Queen Pawn Game Mode for Chessno.

Game Setup:
- A symmetrical, high-stakes battle between Queens and Pawns.
- Initial board layout:
  * White pawns span ranks a4 to h4 (rank 4).
  * Black pawns span ranks a5 to h5 (rank 5).
  * Queens occupy their default starting squares:
      - White Queen on d1.
      - Black Queen on d8.
  * No Kings, Rooks, Bishops, or Knights on the initial board.
- Symmetrical FEN: "3q4/8/8/pppppppp/PPPPPPPP/8/8/3Q4 w - - 0 1"

Game Rules & Win Conditions:
1. Standard chess movement:
   - Queens move across ranks, files, and diagonals.
   - Pawns move 1 square forward (when unblocked) and capture 1 square diagonally forward.
   - Pawns that reach the opponent's back rank (rank 8 for White, rank 1 for Black)
     promote via the standard promotion modal (Queen, Rook, Bishop, Knight).
2. Pawn Elimination & Victory:
   - The main rule: ALL enemy pawns must be captured to win!
   - Capturing the opponent's Queen does NOT end the game; play continues!
   - If White captures all Black pawns while White still has pawns, White wins!
   - If Black captures all White pawns while Black still has pawns, Black wins!
   - If all pawns on both sides are eliminated, or only Queens remain, the game ends in a Tie!
   - Standard 50-move rule, threefold repetition, and timer timeouts apply.
"""

from typing import Optional, List, Dict, Any
import chess

from game_engine import GameMode, GameState, MoveResult


class QueenPawnMode(GameMode):
    """
    Implements the Queen Pawn Game variant for Chessno.
    """

    INITIAL_FEN = "3q4/8/8/pppppppp/PPPPPPPP/8/8/3Q4 w - - 0 1"

    def __init__(self):
        super().__init__(name="Queen Pawn")
        self._winner: Optional[chess.Color] = None
        self._game_over_reason: Optional[str] = None

    def on_init(self, game_state: GameState) -> None:
        """Set up the Queen Pawn starting board position and state."""
        game_state.board = chess.Board(self.INITIAL_FEN)
        self._winner = None
        self._game_over_reason = None

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """Inspect the executed move for pawn elimination and game-ending conditions."""
        # Queen captures do NOT end the game. Check overall game status.
        if self.is_game_over(game_state):
            if self._winner is not None:
                move_result.is_checkmate = True
            else:
                move_result.is_draw = True
                move_result.draw_reason = self._game_over_reason

    def is_game_over(self, game_state: GameState) -> bool:
        """
        Game ends when:
        1. All pawns of one player are captured (the player with pawns remaining wins).
        2. Only Queens remain on the board (both sides have 0 pawns) -> Tie / Draw.
        3. A player has no legal moves left on their turn.
        4. Standard 50-move rule, threefold repetition, or timeout.
        """
        if self._winner is not None or (self._game_over_reason is not None and "Tie" in self._game_over_reason):
            return True

        w_pawns = list(game_state.board.pieces(chess.PAWN, chess.WHITE))
        b_pawns = list(game_state.board.pieces(chess.PAWN, chess.BLACK))
        w_queens = list(game_state.board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = list(game_state.board.pieces(chess.QUEEN, chess.BLACK))

        # 1. Both sides have 0 pawns -> Tie if only queens remain (or no pawns remain)
        if len(w_pawns) == 0 and len(b_pawns) == 0:
            self._winner = None
            if len(w_queens) > 0 or len(b_queens) > 0:
                self._game_over_reason = "Tie! Only Queens remain"
            else:
                self._game_over_reason = "Tie! All pawns captured"
            return True

        # 2. Black has 0 pawns, White still has pawns -> White wins!
        if len(b_pawns) == 0 and len(w_pawns) > 0:
            self._winner = chess.WHITE
            self._game_over_reason = "White wins! All Black pawns captured"
            return True

        # 3. White has 0 pawns, Black still has pawns -> Black wins!
        if len(w_pawns) == 0 and len(b_pawns) > 0:
            self._winner = chess.BLACK
            self._game_over_reason = "Black wins! All White pawns captured"
            return True

        # 4. Check if player whose turn it is has no legal moves (Stalemate)
        if not any(game_state.board.generate_legal_moves()):
            if len(w_pawns) > len(b_pawns):
                self._winner = chess.WHITE
                self._game_over_reason = "White wins by pawn advantage (No legal moves)"
            elif len(b_pawns) > len(w_pawns):
                self._winner = chess.BLACK
                self._game_over_reason = "Black wins by pawn advantage (No legal moves)"
            else:
                self._winner = None
                self._game_over_reason = "Draw by Stalemate (No legal moves)"
            return True

        if game_state.board.is_fifty_moves():
            self._winner = None
            self._game_over_reason = "Draw by 50-Move Rule"
            return True

        if game_state.board.is_repetition(3):
            self._winner = None
            self._game_over_reason = "Draw by Threefold Repetition"
            return True

        return False

    def winner(self, game_state: GameState) -> Optional[chess.Color]:
        """Return the winner of the Queen Pawn match, or None if drawn/ongoing."""
        if self._winner is not None:
            return self._winner
        self.is_game_over(game_state)
        return self._winner

    def game_over_reason(self, game_state: GameState) -> Optional[str]:
        """Return the descriptive game over reason string, or None."""
        if self._game_over_reason is not None:
            return self._game_over_reason
        self.is_game_over(game_state)
        return self._game_over_reason

    def royal_square(self, game_state: GameState, color: chess.Color) -> Optional[chess.Square]:
        """Return the Queen's square for the specified player, if alive on the board."""
        queens = list(game_state.board.pieces(chess.QUEEN, color))
        return queens[0] if queens else None

    def is_in_check(self, game_state: GameState) -> bool:
        """Return True if the current active player's Queen is directly threatened."""
        active_color = game_state.board.turn
        opp_color = chess.BLACK if active_color == chess.WHITE else chess.WHITE
        queens = list(game_state.board.pieces(chess.QUEEN, active_color))
        return any(game_state.board.is_attacked_by(opp_color, sq) for sq in queens)

    def is_queen_under_attack(self, game_state: GameState, color: chess.Color) -> bool:
        """True if the Queen of `color` is attacked by opponent pieces."""
        opp_color = chess.BLACK if color == chess.WHITE else chess.WHITE
        queens = list(game_state.board.pieces(chess.QUEEN, color))
        return any(game_state.board.is_attacked_by(opp_color, sq) for sq in queens)

    def get_queen_square(self, game_state: GameState, color: chess.Color) -> Optional[chess.Square]:
        """Return the location square of the given color's Queen."""
        return self.royal_square(game_state, color)

    def get_queen_count(self, game_state: GameState, color: chess.Color) -> int:
        """Return the number of active Queens for the given color."""
        return len(list(game_state.board.pieces(chess.QUEEN, color)))

    def get_pawn_count(self, game_state: GameState, color: chess.Color) -> int:
        """Return the number of active Pawns for the given color."""
        return len(list(game_state.board.pieces(chess.PAWN, color)))

    def get_status_message(self, game_state: GameState) -> Optional[str]:
        """Contextual status message for header and HUD."""
        if self.is_game_over(game_state):
            return self.game_over_reason(game_state)
        turn_str = game_state.turn_name
        if self.is_in_check(game_state):
            return f"Danger! {turn_str} Queen is under Attack!"
        return f"{turn_str}'s Turn"
