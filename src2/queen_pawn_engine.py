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

Game Rules & Movement:
1. Standard chess movement:
   - Queens move across ranks, files, and diagonals.
   - Pawns move 1 square forward (when unblocked) and capture 1 square diagonally forward.
   - Pawns that reach the opponent's back rank (rank 8 for White, rank 1 for Black)
     promote via the standard promotion modal (Queen, Rook, Bishop, Knight).
2. Royal objective & Win conditions:
   - The Queen serves as the commanding royal piece.
   - Capturing the opponent's Queen (when they have no other Queens on the board)
     results in an immediate win for the capturer!
   - If a player runs out of legal moves on their turn, the opponent wins.
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
        """Inspect the executed move for Queen captures or end-of-game conditions."""
        if move_result.captured_piece and move_result.captured_piece.piece_type == chess.QUEEN:
            # Check if the opponent has any remaining Queens
            opp_color = chess.BLACK if move_result.piece_moved.color == chess.WHITE else chess.WHITE
            opp_queens = list(game_state.board.pieces(chess.QUEEN, opp_color))
            if len(opp_queens) == 0:
                self._winner = move_result.piece_moved.color
                winner_name = "White" if self._winner == chess.WHITE else "Black"
                self._game_over_reason = f"Queen Captured! {winner_name} wins!"
                move_result.is_checkmate = True

        # Check if the opponent now has no legal moves
        if not self._winner:
            turn = game_state.board.turn
            if not any(game_state.board.generate_legal_moves()):
                self._winner = chess.BLACK if turn == chess.WHITE else chess.WHITE
                w_name = "Black" if self._winner == chess.BLACK else "White"
                l_name = "White" if turn == chess.WHITE else "Black"
                self._game_over_reason = f"{l_name} has no legal moves! {w_name} wins"
                move_result.is_checkmate = True

    def is_game_over(self, game_state: GameState) -> bool:
        """Return True if either side has lost their Queen(s) or cannot make a legal move."""
        if self._winner is not None:
            return True

        w_queens = list(game_state.board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = list(game_state.board.pieces(chess.QUEEN, chess.BLACK))

        if len(w_queens) == 0:
            self._winner = chess.BLACK
            self._game_over_reason = "Queen Captured! Black wins!"
            return True

        if len(b_queens) == 0:
            self._winner = chess.WHITE
            self._game_over_reason = "Queen Captured! White wins!"
            return True

        turn = game_state.board.turn
        if not any(game_state.board.generate_legal_moves()):
            self._winner = chess.BLACK if turn == chess.WHITE else chess.WHITE
            w_name = "Black" if self._winner == chess.BLACK else "White"
            l_name = "White" if turn == chess.WHITE else "Black"
            self._game_over_reason = f"{l_name} has no legal moves! {w_name} wins"
            return True

        if game_state.board.is_fifty_moves():
            self._game_over_reason = "Draw by 50-Move Rule"
            return True

        if game_state.board.is_repetition(3):
            self._game_over_reason = "Draw by Threefold Repetition"
            return True

        return False

    def winner(self, game_state: GameState) -> Optional[chess.Color]:
        """Return the winner of the Queen Pawn match, or None."""
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
        """Return the primary Queen's square for the specified player, if alive."""
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
