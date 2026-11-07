# rook_dash_engine.py
"""
Rook Dash Game Mode for Chessno.

Game Setup:
- Only 2 Rooks, 8 Pawns, and 1 King per side on their default initial positions.
  * White: Rooks on a1, h1; King on e1; Pawns on a2-h2.
  * Black: Rooks on a8, h8; King on e8; Pawns on a7-h7.
  * No Knights, Bishops, or Queens.
- Symmetrical FEN: "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w - - 0 1"

Game Rules & Movement:
1. Rooks have only 4 directional choices: Left, Right, Up, Down.
   When moving in a direction, the Rook DASHES as far as possible:
   - It stops when obstructed by the boundary of the board.
   - It stops immediately before any friendly piece (pawn, king, rook).
   - It hits and captures the first enemy piece in its path.
   - It cannot stop on intermediate squares along the ray.
2. Pawns move and capture using standard chess rules.
3. Kings move 1 square in any direction using standard chess rules.
4. Pawn Promotion: Pawns can ONLY promote to Rooks.
5. Win Condition: First to deliver checkmate wins!
"""

from typing import Optional, List, Dict, Any, Tuple
import chess

from game_engine import GameMode, GameState, MoveResult


class RookDashMode(GameMode):
    """
    Implements the high-speed 'Rook Dash' chess variant for Chessno.
    """

    INITIAL_FEN = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w - - 0 1"

    def __init__(self):
        super().__init__(name="Rook Dash")
        self.auto_promotion_piece: Optional[int] = chess.ROOK
        self.default_promotion_piece: Optional[int] = chess.ROOK
        self._winner: Optional[chess.Color] = None
        self._game_over_reason: Optional[str] = None

    def on_init(self, game_state: GameState) -> None:
        """Set up the initial Rook Dash board layout and reset status."""
        game_state.board = chess.Board(self.INITIAL_FEN)
        self._winner = None
        self._game_over_reason = None

    @staticmethod
    def get_rook_dash_destinations(board: chess.Board, from_sq: chess.Square) -> List[chess.Square]:
        """
        Calculate the exact destination squares for a Rook in the 4 cardinal directions:
        Up, Down, Left, Right.
        The Rook dashes until it hits:
        - The boundary of the board.
        - A friendly piece (it stops at the square immediately before it).
        - An enemy piece (it captures the enemy piece and stops on its square).
        Returns a list of at most 4 destination squares.
        """
        piece = board.piece_at(from_sq)
        if piece is None or piece.piece_type != chess.ROOK:
            return []

        f0 = chess.square_file(from_sq)
        r0 = chess.square_rank(from_sq)
        color = piece.color

        directions: List[Tuple[int, int]] = [
            (0, 1),   # Up
            (0, -1),  # Down
            (-1, 0),  # Left
            (1, 0),   # Right
        ]
        destinations: List[chess.Square] = []

        for df, dr in directions:
            s = 1
            last_empty: Optional[chess.Square] = None
            while True:
                f = f0 + s * df
                r = r0 + s * dr
                if not (0 <= f <= 7 and 0 <= r <= 7):
                    # Reached off-board boundary: last empty square was at the edge!
                    if last_empty is not None:
                        destinations.append(last_empty)
                    break

                sq = chess.square(f, r)
                p = board.piece_at(sq)
                if p is None:
                    last_empty = sq
                    # Check if this square is already at the physical border
                    if not (0 <= f + df <= 7 and 0 <= r + dr <= 7):
                        destinations.append(sq)
                        break
                    s += 1
                else:
                    if p.color == color:
                        # Obstructed by friendly piece: stop on the square right before it!
                        if last_empty is not None:
                            destinations.append(last_empty)
                    else:
                        # Enemy piece encountered: hit and capture it!
                        destinations.append(sq)
                    break

        return destinations

    def can_move(
        self,
        arg1: Any,
        arg2: Optional[Any] = None,
        board: Optional[chess.Board] = None,
    ) -> bool:
        """
        Filter moves according to Rook Dash rules:
        - Rooks can only move to their designated dash destination in one of the 4 directions.
        - Pawns can only promote to Rooks.
        Supports both can_move(game_state, move) and can_move(move, board=board).
        """
        if isinstance(arg1, chess.Move):
            move = arg1
            b = board if board is not None else (arg2 if isinstance(arg2, chess.Board) else None)
        else:
            move = arg2
            b = getattr(arg1, "board", None) if arg1 is not None else board

        if b is None or move is None:
            return True

        piece = b.piece_at(move.from_square)
        if piece is None:
            return False

        # 1. Rook Dashing Constraint
        if piece.piece_type == chess.ROOK:
            dash_dests = self.get_rook_dash_destinations(b, move.from_square)
            return move.to_square in dash_dests

        # 2. Pawn Promotion Constraint: Only Rooks allowed
        if piece.piece_type == chess.PAWN:
            if move.promotion is not None and move.promotion != chess.ROOK:
                return False

        return True

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """Inspect the executed move for game-ending conditions."""
        if self.is_game_over(game_state):
            if self._winner is not None:
                move_result.is_checkmate = True
            else:
                move_result.is_draw = True
                move_result.draw_reason = self._game_over_reason

    def is_game_over(self, game_state: GameState) -> bool:
        """
        Game ends when:
        1. A player is checkmated (king in check and 0 valid dash/pawn/king moves).
        2. Stalemate (0 valid moves, not in check).
        3. Standard draw conditions (50-move rule, threefold repetition, timeout).
        """
        if self._winner is not None or self._game_over_reason is not None:
            return True

        valid_moves = []
        for m in game_state.board.legal_moves:
            if self.can_move(game_state, m):
                valid_moves.append(m)

        if not valid_moves:
            if game_state.board.is_check():
                self._winner = chess.BLACK if game_state.board.turn == chess.WHITE else chess.WHITE
                winner_name = "Black" if self._winner == chess.BLACK else "White"
                self._game_over_reason = f"Checkmate! {winner_name} wins by Rook Dash checkmate"
            else:
                self._winner = None
                self._game_over_reason = "Draw by Stalemate"
            return True

        if game_state.board.is_insufficient_material():
            self._winner = None
            self._game_over_reason = "Draw by Insufficient Material"
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
        """Return the winner of the Rook Dash match, or None if drawn/ongoing."""
        return self._winner

    def game_over_reason(self, game_state: GameState) -> Optional[str]:
        """Human-readable explanation of match conclusion."""
        return self._game_over_reason

    def get_status_message(self, game_state: GameState) -> Optional[str]:
        """Custom one-line status summary for the game HUD."""
        if game_state.is_in_check():
            return f"{game_state.turn_name} is in Check! Dash to safety or block!"
        w_rooks = len(list(game_state.board.pieces(chess.ROOK, chess.WHITE)))
        b_rooks = len(list(game_state.board.pieces(chess.ROOK, chess.BLACK)))
        return f"{game_state.turn_name}'s Turn (Rooks: White {w_rooks} vs Black {b_rooks})"
