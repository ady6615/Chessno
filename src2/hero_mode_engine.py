# hero_mode_engine.py
"""
Hero Mode Game Variant for Chessno.

Game Setup:
- Only 1 Hero (represented by Queen with combined Queen + Knight moves),
  8 Pawns, and 1 King per side on their default initial positions.
  * White: Hero on d1; King on e1; Pawns on a2-h2.
  * Black: Hero on d8; King on e8; Pawns on a7-h7.
  * No Knights, Bishops, or Rooks on the board.
- Symmetrical FEN: "3qk3/pppppppp/8/8/8/8/PPPPPPPP/3QK3 w - - 0 1"

Game Rules & Movement:
1. The Hero Piece:
   - Moves as both a Queen AND a Knight combined (the legendary 'Amazon' fairy chess piece).
   - Can sweep across orthogonal ranks/files and diagonal lines of sight (Queen rays).
   - Can jump over any intervening pieces in L-shaped jumps (Knight leaps).
   - Captures any enemy piece by landing on its square via either movement mode.
2. Pawns:
   - Move 1 or 2 squares forward initially, capture diagonally, and can execute En Passant.
   - Promote strictly to Hero pieces (Queen) upon reaching the back rank.
3. Kings:
   - Move 1 square in any direction. No castling (no rooks).
4. Check & Checkmate:
   - A King is in check when attacked by an enemy piece, including Hero knight-jumps and rays.
   - Kings cannot move into check or remain in check.
   - First to deliver checkmate wins!
"""

from typing import Optional, List, Dict, Any, Tuple
import chess

from game_engine import GameMode, GameState, MoveResult


class HeroMode(GameMode):
    """
    Implements the 'Hero Mode' (Queen + Knight Amazon compound piece) variant.
    """

    INITIAL_FEN = "3qk3/pppppppp/8/8/8/8/PPPPPPPP/3QK3 w - - 0 1"

    # 8 Knight L-shape leap offsets
    KNIGHT_OFFSETS = [
        (1, 2), (2, 1), (-1, 2), (-2, 1),
        (1, -2), (2, -1), (-1, -2), (-2, -1),
    ]

    # 8 Queen orthogonal and diagonal ray directions
    QUEEN_DIRECTIONS = [
        (0, 1), (0, -1), (1, 0), (-1, 0),
        (1, 1), (-1, 1), (1, -1), (-1, -1),
    ]

    def __init__(self):
        super().__init__(name="Hero Mode")
        self.auto_promotion_piece: Optional[int] = chess.QUEEN
        self.default_promotion_piece: Optional[int] = chess.QUEEN
        self._winner: Optional[chess.Color] = None
        self._game_over_reason: Optional[str] = None

    def on_init(self, game_state: GameState) -> None:
        """Set up the initial Hero Mode board layout and state."""
        game_state.board = chess.Board(self.INITIAL_FEN)
        game_state.board.castling_rights = 0
        self._winner = None
        self._game_over_reason = None

    @classmethod
    def is_square_attacked_by(
        cls,
        board: chess.Board,
        target_sq: chess.Square,
        attacking_color: chess.Color,
    ) -> bool:
        """
        Return True if `target_sq` is attacked by any piece belonging to `attacking_color`.
        Factors in:
        - Hero piece (Queen): both Queen rays and Knight L-shape jumps
        - Pawns: diagonal forward capture squares
        - King: adjacent squares
        - Standard pieces if any exist (knights, bishops, rooks)
        """
        tf = chess.square_file(target_sq)
        tr = chess.square_rank(target_sq)

        # 1. Pawn attacks
        pawn_dir = 1 if attacking_color == chess.WHITE else -1
        source_rank = tr - pawn_dir
        if 0 <= source_rank <= 7:
            for df in (-1, 1):
                pf = tf + df
                if 0 <= pf <= 7:
                    p = board.piece_at(chess.square(pf, source_rank))
                    if p and p.piece_type == chess.PAWN and p.color == attacking_color:
                        return True

        # 2. Hero (Queen) attacks: Queen rays + Knight jumps
        for sq in board.pieces(chess.QUEEN, attacking_color):
            qf = chess.square_file(sq)
            qr = chess.square_rank(sq)
            df = abs(qf - tf)
            dr = abs(qr - tr)

            # A) Knight-jump attack
            if (df == 1 and dr == 2) or (df == 2 and dr == 1):
                return True

            # B) Queen ray attack (orthogonal or diagonal line of sight)
            if df == 0 or dr == 0 or df == dr:
                step_f = 0 if df == 0 else (1 if tf > qf else -1)
                step_r = 0 if dr == 0 else (1 if tr > qr else -1)
                cur_f = qf + step_f
                cur_r = qr + step_r
                blocked = False
                while (cur_f != tf or cur_r != tr):
                    if board.piece_at(chess.square(cur_f, cur_r)) is not None:
                        blocked = True
                        break
                    cur_f += step_f
                    cur_r += step_r
                if not blocked:
                    return True

        # 3. King attacks
        ksq = board.king(attacking_color)
        if ksq is not None:
            kf = chess.square_file(ksq)
            kr = chess.square_rank(ksq)
            if max(abs(kf - tf), abs(kr - tr)) <= 1:
                return True

        # 4. Standard Knights, Bishops, Rooks (fallback if ever present)
        for sq in board.pieces(chess.KNIGHT, attacking_color):
            kf = chess.square_file(sq)
            kr = chess.square_rank(sq)
            if (abs(kf - tf), abs(kr - tr)) in ((1, 2), (2, 1)):
                return True

        for sq in board.pieces(chess.BISHOP, attacking_color):
            bf = chess.square_file(sq)
            br = chess.square_rank(sq)
            if abs(bf - tf) == abs(br - tr):
                step_f = 1 if tf > bf else -1
                step_r = 1 if tr > br else -1
                cur_f, cur_r = bf + step_f, br + step_r
                blocked = False
                while (cur_f != tf or cur_r != tr):
                    if board.piece_at(chess.square(cur_f, cur_r)) is not None:
                        blocked = True
                        break
                    cur_f += step_f
                    cur_r += step_r
                if not blocked:
                    return True

        for sq in board.pieces(chess.ROOK, attacking_color):
            rf = chess.square_file(sq)
            rr = chess.square_rank(sq)
            if rf == tf or rr == tr:
                step_f = 0 if rf == tf else (1 if tf > rf else -1)
                step_r = 0 if rr == tr else (1 if tr > rr else -1)
                cur_f, cur_r = rf + step_f, rr + step_r
                blocked = False
                while (cur_f != tf or cur_r != tr):
                    if board.piece_at(chess.square(cur_f, cur_r)) is not None:
                        blocked = True
                        break
                    cur_f += step_f
                    cur_r += step_r
                if not blocked:
                    return True

        return False

    def is_in_check(self, game_state_or_board: Any, color: Optional[chess.Color] = None) -> bool:
        """Return True if the specified player's King is currently in check."""
        b = game_state_or_board.board if hasattr(game_state_or_board, "board") else game_state_or_board
        target_color = b.turn if color is None else color
        ksq = b.king(target_color)
        if ksq is None:
            return False
        return self.is_square_attacked_by(b, ksq, not target_color)

    def get_pseudo_legal_moves_for_piece(
        self,
        board: chess.Board,
        from_sq: chess.Square,
    ) -> List[chess.Move]:
        """Generate all pseudo-legal moves for the piece at `from_sq`."""
        piece = board.piece_at(from_sq)
        if piece is None or piece.color != board.turn:
            return []

        moves: List[chess.Move] = []
        color = piece.color
        f0 = chess.square_file(from_sq)
        r0 = chess.square_rank(from_sq)

        # 1. Hero Piece (Queen: Queen rays + Knight jumps)
        if piece.piece_type == chess.QUEEN:
            # A) Queen straight and diagonal rays
            for df, dr in self.QUEEN_DIRECTIONS:
                for step in range(1, 8):
                    f = f0 + step * df
                    r = r0 + step * dr
                    if not (0 <= f <= 7 and 0 <= r <= 7):
                        break
                    target_sq = chess.square(f, r)
                    dest_p = board.piece_at(target_sq)
                    if dest_p is None:
                        moves.append(chess.Move(from_sq, target_sq))
                    elif dest_p.color != color:
                        moves.append(chess.Move(from_sq, target_sq))
                        break
                    else:
                        break

            # B) Knight L-shaped jumps
            for df, dr in self.KNIGHT_OFFSETS:
                f = f0 + df
                r = r0 + dr
                if 0 <= f <= 7 and 0 <= r <= 7:
                    target_sq = chess.square(f, r)
                    dest_p = board.piece_at(target_sq)
                    if dest_p is None or dest_p.color != color:
                        moves.append(chess.Move(from_sq, target_sq))

        # 2. Pawn Piece
        elif piece.piece_type == chess.PAWN:
            forward_dir = 1 if color == chess.WHITE else -1
            start_rank = 1 if color == chess.WHITE else 6
            promo_rank = 7 if color == chess.WHITE else 0

            # Single step forward
            r_one = r0 + forward_dir
            if 0 <= r_one <= 7:
                sq_one = chess.square(f0, r_one)
                if board.piece_at(sq_one) is None:
                    if r_one == promo_rank:
                        moves.append(chess.Move(from_sq, sq_one, promotion=chess.QUEEN))
                    else:
                        moves.append(chess.Move(from_sq, sq_one))

                    # Double step from starting rank
                    if r0 == start_rank:
                        r_two = r0 + 2 * forward_dir
                        sq_two = chess.square(f0, r_two)
                        if board.piece_at(sq_two) is None:
                            moves.append(chess.Move(from_sq, sq_two))

            # Diagonal captures & En Passant
            for df in (-1, 1):
                f_diag = f0 + df
                r_diag = r0 + forward_dir
                if 0 <= f_diag <= 7 and 0 <= r_diag <= 7:
                    diag_sq = chess.square(f_diag, r_diag)
                    target_p = board.piece_at(diag_sq)
                    is_ep = (diag_sq == board.ep_square)

                    if (target_p is not None and target_p.color != color) or is_ep:
                        if r_diag == promo_rank:
                            moves.append(chess.Move(from_sq, diag_sq, promotion=chess.QUEEN))
                        else:
                            moves.append(chess.Move(from_sq, diag_sq))

        # 3. King Piece
        elif piece.piece_type == chess.KING:
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    f = f0 + df
                    r = r0 + dr
                    if 0 <= f <= 7 and 0 <= r <= 7:
                        target_sq = chess.square(f, r)
                        dest_p = board.piece_at(target_sq)
                        if dest_p is None or dest_p.color != color:
                            moves.append(chess.Move(from_sq, target_sq))

        return moves

    def get_legal_moves_from(
        self,
        game_state_or_board: Any,
        square: chess.Square,
    ) -> List[chess.Move]:
        """
        Return all strictly legal moves originating from `square`.
        Filters pseudo-legal moves to ensure the mover's King is not left in check.
        """
        board = game_state_or_board.board if hasattr(game_state_or_board, "board") else game_state_or_board
        piece = board.piece_at(square)
        if piece is None or piece.color != board.turn:
            return []

        pseudo_moves = self.get_pseudo_legal_moves_for_piece(board, square)
        legal_moves: List[chess.Move] = []
        mover_color = board.turn

        for move in pseudo_moves:
            test_b = board.copy(stack=False)
            test_b.push(move)
            ksq = test_b.king(mover_color)
            if ksq is not None and not self.is_square_attacked_by(test_b, ksq, not mover_color):
                legal_moves.append(move)

        return legal_moves

    def get_legal_moves(self, board: chess.Board) -> List[chess.Move]:
        """Return all legal moves for the active side on the given board."""
        all_moves: List[chess.Move] = []
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if p and p.color == board.turn:
                all_moves.extend(self.get_legal_moves_from(board, sq))
        return all_moves

    def is_legal_move(
        self,
        game_state_or_board: Any,
        from_square: chess.Square,
        to_square: Optional[chess.Square] = None,
        promotion: Optional[int] = None,
    ) -> bool:
        """Validate if moving between the two squares is legal under Hero Mode rules."""
        if isinstance(from_square, chess.Move):
            m = from_square
            from_sq, to_sq, promo = m.from_square, m.to_square, m.promotion
        else:
            from_sq = from_square
            to_sq = to_square
            promo = promotion

        legal_moves = self.get_legal_moves_from(game_state_or_board, from_sq)
        for cand in legal_moves:
            if cand.from_square == from_sq and cand.to_square == to_sq:
                if promo is None or cand.promotion == promo:
                    return True
        return False

    def can_move(
        self,
        arg1: Any,
        arg2: Optional[Any] = None,
        board: Optional[chess.Board] = None,
    ) -> bool:
        """Compatibility filter hook for AI bot and game validator hooks."""
        if isinstance(arg1, chess.Move):
            move = arg1
            b = board if board is not None else (arg2 if isinstance(arg2, chess.Board) else None)
        else:
            move = arg2
            b = getattr(arg1, "board", None) if arg1 is not None else board

        if b is None or move is None:
            return True

        return self.is_legal_move(b, move.from_square, move.to_square, move.promotion)

    def is_game_over(self, game_state_or_board: Any) -> bool:
        """
        Check game-ending conditions:
        1. Checkmate (0 legal moves and King in check)
        2. Stalemate (0 legal moves and King not in check)
        3. 50-move rule, threefold repetition, insufficient material
        """
        if self._winner is not None or self._game_over_reason is not None:
            return True

        board = game_state_or_board.board if hasattr(game_state_or_board, "board") else game_state_or_board

        legal_moves = self.get_legal_moves(board)
        if not legal_moves:
            if self.is_in_check(board):
                self._winner = not board.turn
                w_str = "White" if self._winner == chess.WHITE else "Black"
                self._game_over_reason = f"Checkmate! {w_str} wins"
            else:
                self._winner = None
                self._game_over_reason = "Draw by Stalemate"
            return True

        if board.is_fifty_moves():
            self._winner = None
            self._game_over_reason = "Draw by 50-Move Rule"
            return True

        if board.is_repetition(3):
            self._winner = None
            self._game_over_reason = "Draw by Repetition"
            return True

        # King vs King insufficient material
        if len(board.piece_map()) <= 2:
            self._winner = None
            self._game_over_reason = "Draw by Insufficient Material"
            return True

        return False

    def winner(self, game_state_or_board: Optional[Any] = None) -> Optional[chess.Color]:
        """Return the winner of the match, or None if ongoing or drawn."""
        return self._winner

    def game_over_reason(self, game_state_or_board: Optional[Any] = None) -> Optional[str]:
        """Return human-readable game termination reason."""
        return self._game_over_reason

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """Inspect the executed move for game-ending conditions or check status."""
        if self.is_game_over(game_state):
            if self._winner is not None:
                move_result.is_checkmate = True
            else:
                move_result.is_draw = True
                move_result.draw_reason = self._game_over_reason
        else:
            move_result.is_check = self.is_in_check(game_state)
