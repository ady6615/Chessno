# atomic_engine.py
"""
Atomic Chess Game Variant for Chessno.

Game Setup:
- Full standard chess starting layout (Kings, Queens, Rooks, Bishops, Knights, Pawns).
- Powered by python-chess variant engine (chess.variant.AtomicBoard).

Atomic Chess Rules:
1. Explosion Mechanic:
   - Every piece capture triggers a devastating atomic explosion centered at the destination square.
   - The explosion immediately destroys and removes:
     * The capturing piece.
     * The captured piece.
     * All pieces on the 8 adjacent squares (orthogonal and diagonal) of BOTH colors, EXCEPT for Pawns.
   - Pawns on surrounding squares are completely immune to the explosion and remain on the board.
   - For en passant captures, the explosion is centered at the destination square where the pawn lands.

2. Winning & Game Over Conditions:
   - King Explosion (Atomic Blast): If a capture's blast wave destroys the opponent's King
     (by capturing any piece directly adjacent to the opponent's King), the capturing player
     wins immediately!
   - Checkmate: The game can also be won by traditional checkmate (attacking the King with no escape).
   - Suicide is strictly illegal: A player is forbidden from making any move/capture that would
     destroy their own King.
   - Kings cannot capture: Because the capturing piece always explodes, Kings are barred from
     capturing any piece directly.
   - Connected Kings: Kings cannot be placed on adjacent squares because neither can capture
     the other without mutual explosion.
"""

from typing import Optional, List, Dict, Any, Tuple
import chess
import chess.variant

from game_engine import GameMode, GameState, MoveResult
from coordinates import piece_to_code


class AtomicChessMode(GameMode):
    """
    Implements the Atomic Chess variant using python-chess AtomicBoard.
    """

    def __init__(self):
        super().__init__(name="Atomic Chess")
        self.last_explosion: Optional[Dict[str, Any]] = None
        self._winner: Optional[chess.Color] = None
        self._game_over_reason: Optional[str] = None

    def on_init(self, game_state: GameState) -> None:
        """Initialize or reset the board to a fresh AtomicBoard."""
        game_state.board = chess.variant.AtomicBoard()
        self.last_explosion = None
        self._winner = None
        self._game_over_reason = None
        # Register pre-move capture calculation hook
        if self._pre_move_capture_hook not in game_state._pre_move_validators:
            game_state.register_pre_move_validator(self._pre_move_capture_hook)

    def _pre_move_capture_hook(self, game_state: GameState, move: chess.Move) -> bool:
        """Calculate explosion details before board.push(move) alters the pieces."""
        if game_state.board.is_capture(move):
            self.last_explosion = self.calculate_explosion(game_state.board, move)
        else:
            self.last_explosion = None
        return True

    def calculate_explosion(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute explosion details before pushing the capture move:
        center square, all affected squares, destroyed pieces, and whether any king is destroyed.
        """
        if not board.is_capture(move):
            return None

        to_sq = move.to_square
        center_f = chess.square_file(to_sq)
        center_r = chess.square_rank(to_sq)

        destroyed_pieces: List[Tuple[chess.Square, chess.Piece]] = []
        affected_squares: List[chess.Square] = [to_sq]

        # 1. Directly captured piece
        captured_piece = board.piece_at(to_sq)
        if board.is_en_passant(move):
            ep_sq = chess.square(center_f, chess.square_rank(move.from_square))
            captured_piece = board.piece_at(ep_sq)
            if ep_sq not in affected_squares:
                affected_squares.append(ep_sq)
            if captured_piece:
                destroyed_pieces.append((ep_sq, captured_piece))
        elif captured_piece:
            destroyed_pieces.append((to_sq, captured_piece))

        # 2. Capturing piece (blown up in the explosion)
        capturing_piece = board.piece_at(move.from_square)
        if capturing_piece:
            destroyed_pieces.append((to_sq, capturing_piece))

        # 3. 8 Adjacent squares (non-pawns are destroyed, pawns survive)
        king_destroyed: Optional[chess.Color] = None
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                nf = center_f + df
                nr = center_r + dr
                if 0 <= nf <= 7 and 0 <= nr <= 7:
                    adj_sq = chess.square(nf, nr)
                    p = board.piece_at(adj_sq)
                    if p is not None and p.piece_type != chess.PAWN:
                        if adj_sq not in affected_squares:
                            affected_squares.append(adj_sq)
                        destroyed_pieces.append((adj_sq, p))
                        if p.piece_type == chess.KING:
                            king_destroyed = p.color

        return {
            "center_square": to_sq,
            "affected_squares": affected_squares,
            "destroyed_pieces": destroyed_pieces,
            "king_destroyed": king_destroyed,
            "capturing_color": board.turn,
        }

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """Record destroyed pieces in captured collections."""
        if self.last_explosion:
            for sq, piece in self.last_explosion.get("destroyed_pieces", []):
                p_code = piece_to_code(piece)
                if not p_code:
                    continue
                # Opponent of piece.color gets it in captured pieces
                cap_color = "w" if piece.color == chess.BLACK else "b"
                if p_code not in game_state.captured_pieces[cap_color]:
                    game_state.captured_pieces[cap_color].append(p_code)

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """Validate move legality under Atomic rules."""
        return move in game_state.board.legal_moves

    def get_legal_moves_from(self, game_state: GameState, square: chess.Square) -> List[chess.Move]:
        """Return all legal atomic moves from the specified square."""
        piece = game_state.board.piece_at(square)
        if piece is None or piece.color != game_state.board.turn:
            return []
        return [m for m in game_state.board.legal_moves if m.from_square == square]

    def is_legal_move(
        self,
        game_state: GameState,
        from_square: chess.Square,
        to_square: chess.Square,
        promotion: Optional[int] = None,
    ) -> bool:
        """Check if move is legal under atomic rules, handling promotion default."""
        promo = promotion
        if promo is None and game_state.needs_promotion(from_square, to_square):
            promo = chess.QUEEN
        move = chess.Move(from_square, to_square, promotion=promo)
        return move in game_state.board.legal_moves

    def is_game_over(self, game_state: GameState) -> bool:
        """True if king was blown up, checkmate, stalemate, or draw."""
        return game_state.board.is_game_over()

    def winner(self, game_state: GameState) -> Optional[chess.Color]:
        """Return winning player color (chess.WHITE, chess.BLACK, or None if ongoing/drawn)."""
        if game_state.board.is_game_over():
            outcome = game_state.board.outcome()
            if outcome and outcome.winner is not None:
                return outcome.winner
        return None

    def game_over_reason(self, game_state: GameState) -> Optional[str]:
        """Descriptive game over explanation."""
        if not game_state.board.is_game_over():
            return None
        outcome = game_state.board.outcome()
        if outcome:
            if outcome.termination in (chess.Termination.VARIANT_LOSS, chess.Termination.VARIANT_WIN):
                winner_str = "White" if outcome.winner == chess.WHITE else "Black"
                loser_str = "Black" if outcome.winner == chess.WHITE else "White"
                return f"Atomic Blast! {loser_str} King was blown up! {winner_str} wins"
            elif outcome.termination == chess.Termination.CHECKMATE:
                winner_str = "White" if outcome.winner == chess.WHITE else "Black"
                return f"Checkmate! {winner_str} wins"
            elif outcome.termination == chess.Termination.STALEMATE:
                return "Draw by Stalemate"
            elif outcome.termination == chess.Termination.INSUFFICIENT_MATERIAL:
                return "Draw by Insufficient Material"
            elif outcome.termination in (chess.Termination.THREEFOLD_REPETITION, chess.Termination.FIVEFOLD_REPETITION):
                return "Draw by Repetition"
            elif outcome.termination in (chess.Termination.FIFTY_MOVES, chess.Termination.SEVENTYFIVE_MOVES):
                return "Draw by 50-Move Rule"
        return "Game Over"

    def is_in_check(self, game_state: GameState) -> bool:
        """Check if the active player is in check."""
        return game_state.board.is_check()

    def royal_square(self, game_state: GameState, color: chess.Color) -> Optional[chess.Square]:
        """Square of king for given color, or None if destroyed."""
        return game_state.board.king(color)
