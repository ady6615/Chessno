# game_engine.py
"""
Game engine for Chessno.

Encapsulates complete chess rules and authoritative state using python-chess.
Provides clean extension hooks for future mods (Chess + UNO, Immortal Snail, Multiplayer).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Callable, Dict, Any
import chess

from coordinates import piece_to_code, board_coords_to_square


@dataclass
class MoveResult:
    """Detailed outcome of an attempted or applied chess move."""
    success: bool
    move: Optional[chess.Move] = None
    san: str = ""
    from_square: Optional[chess.Square] = None
    to_square: Optional[chess.Square] = None
    piece_moved: Optional[chess.Piece] = None
    captured_piece: Optional[chess.Piece] = None
    is_capture: bool = False
    is_castling: bool = False
    is_en_passant: bool = False
    is_promotion: bool = False
    promotion_piece_type: Optional[int] = None
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    is_insufficient_material: bool = False
    is_fifty_moves: bool = False
    is_repetition: bool = False
    is_draw: bool = False
    draw_reason: Optional[str] = None
    error_message: Optional[str] = None


class GameMode:
    """Base class for all chess game modes (Classic, Chess + UNO, Immortal Snail, etc.)."""
    def __init__(self, name: str = "Classic"):
        self.name = name

    def on_init(self, game_state: "GameState") -> None:
        """Called when a game is initialized or reset."""
        pass

    def can_move(self, game_state: "GameState", move: chess.Move) -> bool:
        """Return False if a mod rule blocks an otherwise legal move."""
        return True

    def on_move_executed(self, game_state: "GameState", move_result: MoveResult) -> None:
        """Called immediately after a move is committed to the board."""
        pass

    def on_turn_change(self, game_state: "GameState") -> None:
        """Called when the turn passes to the next player."""
        pass

    def get_overlay_entities(self, game_state: "GameState") -> List[Dict[str, Any]]:
        """Return any extra mod entities (e.g., snail, hazards, card icons) to render."""
        return []


class ClassicChessMode(GameMode):
    """Standard, unmodified FIDE chess."""
    def __init__(self):
        super().__init__(name="Classic")


class GameState:
    """
    Authoritative state of the chess game.
    Uses python-chess for complete, robust rule enforcement.
    """
    def __init__(self, mode: Optional[GameMode] = None, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.mode = mode or ClassicChessMode()
        self.move_history: List[MoveResult] = []
        # Captured pieces lists stored as project piece codes ('wp', 'bn', etc.)
        self.captured_pieces: Dict[str, List[str]] = {"w": [], "b": []}
        self.last_move: Optional[Tuple[chess.Square, chess.Square]] = None
        
        # Mod hooks list
        self._pre_move_validators: List[Callable[["GameState", chess.Move], bool]] = []
        self._post_move_hooks: List[Callable[["GameState", MoveResult], None]] = []

        # Time control timeout state
        self.timeout_winner: Optional[chess.Color] = None
        self.timeout_reason: Optional[str] = None

        self.mode.on_init(self)

    # -------------------------------------------------------------------------
    # State Queries
    # -------------------------------------------------------------------------

    @property
    def turn(self) -> chess.Color:
        """chess.WHITE or chess.BLACK."""
        return self.board.turn

    @property
    def turn_name(self) -> str:
        """'White' or 'Black'."""
        return "White" if self.board.turn == chess.WHITE else "Black"

    @property
    def fullmove_number(self) -> int:
        return self.board.fullmove_number

    def get_piece_at(self, square: chess.Square) -> Optional[chess.Piece]:
        return self.board.piece_at(square)

    def get_piece_code_at(self, square: chess.Square) -> Optional[str]:
        return piece_to_code(self.board.piece_at(square))

    def king_square(self, color: Optional[chess.Color] = None) -> Optional[chess.Square]:
        """Return the square of the king for the given color (default: current player's king)."""
        target_color = self.board.turn if color is None else color
        if hasattr(self.mode, "royal_square"):
            mod_sq = self.mode.royal_square(self, target_color)
            if mod_sq is not None:
                return mod_sq
        return self.board.king(target_color)

    def is_in_check(self) -> bool:
        """True if the player whose turn it is is currently in check or under threat."""
        if hasattr(self.mode, "is_in_check"):
            return self.mode.is_in_check(self)
        return self.board.is_check()

    def set_mode(self, mode: GameMode) -> None:
        """Switch active game mode and initialize it."""
        self.mode = mode
        self.mode.on_init(self)

    def set_timeout(self, loser_color: chess.Color) -> None:
        """Register a match defeat by time expiration."""
        self.timeout_winner = chess.BLACK if loser_color == chess.WHITE else chess.WHITE
        winner_str = "Black" if loser_color == chess.WHITE else "White"
        self.timeout_reason = f"Time Out! {winner_str} wins on time"

    def is_game_over(self) -> bool:
        """True if game is over by checkmate, timeout, any draw condition, or mod condition."""
        if self.timeout_winner is not None:
            return True
        if hasattr(self.mode, "is_game_over") and self.mode.is_game_over(self):
            return True
        if hasattr(self.mode, "moves_remaining") and self.mode.moves_remaining > 0:
            return False
        return (
            self.board.is_checkmate()
            or self.board.is_stalemate()
            or self.board.is_insufficient_material()
            or self.board.is_fifty_moves()
            or self.board.is_repetition(3)
        )

    def winner(self) -> Optional[chess.Color]:
        """Returns chess.WHITE, chess.BLACK, or None if drawn or ongoing."""
        if self.timeout_winner is not None:
            return self.timeout_winner
        if hasattr(self.mode, "winner"):
            mod_winner = self.mode.winner(self)
            if mod_winner is not None:
                return mod_winner
        if self.board.is_checkmate():
            return chess.BLACK if self.board.turn == chess.WHITE else chess.WHITE
        return None

    def game_over_reason(self) -> Optional[str]:
        """Human-readable string explaining why the game is over, or None."""
        if self.timeout_reason is not None:
            return self.timeout_reason
        if hasattr(self.mode, "game_over_reason"):
            mod_reason = self.mode.game_over_reason(self)
            if mod_reason is not None:
                return mod_reason
        if not self.is_game_over():
            return None

        if self.board.is_checkmate():
            winner_str = "Black" if self.board.turn == chess.WHITE else "White"
            return f"Checkmate! {winner_str} wins"
        if self.board.is_stalemate():
            return "Draw by Stalemate"
        if self.board.is_insufficient_material():
            return "Draw by Insufficient Material"
        if self.board.is_fifty_moves():
            return "Draw by 50-Move Rule"
        if self.board.is_repetition(3):
            return "Draw by Threefold Repetition"
        
        return "Game Over"

    def status_summary(self) -> str:
        """Concise one-line summary of current game state."""
        if self.is_game_over():
            return self.game_over_reason() or "Game Over"
        if hasattr(self.mode, "get_status_message"):
            msg = self.mode.get_status_message(self)
            if msg:
                return msg
        if self.is_in_check():
            return f"{self.turn_name} is in Check!"
        return f"{self.turn_name}'s Turn"

    # -------------------------------------------------------------------------
    # Legal Moves & Promotion
    # -------------------------------------------------------------------------

    def get_legal_moves_from(self, square: chess.Square) -> List[chess.Move]:
        """Return all legal moves originating from the given square."""
        if self.board.piece_at(square) is None:
            return []
        
        # Only pieces belonging to the current player can move
        if self.board.piece_at(square).color != self.board.turn:
            return []

        moves = [m for m in self.board.legal_moves if m.from_square == square]

        # Filter through active mode and custom validators
        valid_moves = []
        for m in moves:
            if not self.mode.can_move(self, m):
                continue
            if not all(validator(self, m) for validator in self._pre_move_validators):
                continue
            valid_moves.append(m)

        return valid_moves

    def get_legal_destinations(self, square: chess.Square) -> List[chess.Square]:
        """Return a unique list of squares that can be legally moved to from `square`."""
        moves = self.get_legal_moves_from(square)
        return list({m.to_square for m in moves})

    def is_legal_move(
        self,
        from_square: chess.Square,
        to_square: chess.Square,
        promotion: Optional[int] = None,
    ) -> bool:
        """Check if moving between the two squares is legal under all rules."""
        # Check standard promotion defaulting to Queen if needed
        promo = promotion
        if promo is None and self.needs_promotion(from_square, to_square):
            promo = chess.QUEEN

        move = chess.Move(from_square, to_square, promotion=promo)
        if move not in self.board.legal_moves:
            return False

        if not self.mode.can_move(self, move):
            return False

        if not all(v(self, move) for v in self._pre_move_validators):
            return False

        return True

    def needs_promotion(self, from_square: chess.Square, to_square: chess.Square) -> bool:
        """
        Return True if a move from `from_square` to `to_square` requires pawn promotion.
        """
        piece = self.board.piece_at(from_square)
        if piece is None or piece.piece_type != chess.PAWN:
            return False

        target_rank = chess.square_rank(to_square)
        if piece.color == chess.WHITE and target_rank == 7:
            # Check if any legal move is a promotion between these squares
            return any(
                m.from_square == from_square and m.to_square == to_square and m.promotion is not None
                for m in self.board.legal_moves
            )
        elif piece.color == chess.BLACK and target_rank == 0:
            return any(
                m.from_square == from_square and m.to_square == to_square and m.promotion is not None
                for m in self.board.legal_moves
            )

        return False

    # -------------------------------------------------------------------------
    # Move Execution
    # -------------------------------------------------------------------------

    def make_move(
        self,
        from_square: chess.Square,
        to_square: chess.Square,
        promotion: Optional[int] = None,
    ) -> MoveResult:
        """
        Attempt to execute a chess move.
        If the move requires promotion and `promotion` is None, defaults to Queen or rejects.
        """
        if self.is_game_over():
            return MoveResult(success=False, error_message="Game is already over.")

        piece = self.board.piece_at(from_square)
        if piece is None:
            return MoveResult(success=False, error_message="No piece at source square.")

        if piece.color != self.board.turn:
            return MoveResult(
                success=False,
                error_message=f"It is {self.turn_name}'s turn.",
            )

        # Check promotion requirement
        is_promo = self.needs_promotion(from_square, to_square)
        promo_type = promotion
        if is_promo and promo_type is None:
            promo_type = chess.QUEEN

        move = chess.Move(from_square, to_square, promotion=promo_type)

        if move not in self.board.legal_moves:
            return MoveResult(success=False, error_message="Illegal chess move.")

        if not self.mode.can_move(self, move):
            return MoveResult(success=False, error_message="Move blocked by game mode rules.")

        if not all(validator(self, move) for validator in self._pre_move_validators):
            return MoveResult(success=False, error_message="Move rejected by validator hook.")

        # Capture metadata before pushing the move
        is_capture = self.board.is_capture(move)
        is_castling = self.board.is_castling(move)
        is_en_passant = self.board.is_en_passant(move)
        
        captured_piece: Optional[chess.Piece] = None
        if is_en_passant:
            # The captured pawn is on the adjacent square, not the destination
            ep_captured_sq = chess.square(chess.square_file(to_square), chess.square_rank(from_square))
            captured_piece = self.board.piece_at(ep_captured_sq)
        elif is_capture:
            captured_piece = self.board.piece_at(to_square)

        san = self.board.san(move)

        # Commit move to the authoritative board
        self.board.push(move)

        # Record captured piece code
        if captured_piece:
            captured_code = piece_to_code(captured_piece)
            # Whichever player captured stores it in their collection
            capturing_color = "w" if piece.color == chess.WHITE else "b"
            if captured_code:
                self.captured_pieces[capturing_color].append(captured_code)

        self.last_move = (from_square, to_square)

        # Compile game outcome flags
        is_check = self.board.is_check()
        is_checkmate = self.board.is_checkmate()
        is_stalemate = self.board.is_stalemate()
        is_insufficient = self.board.is_insufficient_material()
        is_fifty = self.board.is_fifty_moves()
        is_rep = self.board.is_repetition(3)
        is_draw = is_stalemate or is_insufficient or is_fifty or is_rep
        draw_reason = None
        if is_draw:
            if is_stalemate:
                draw_reason = "Stalemate"
            elif is_insufficient:
                draw_reason = "Insufficient Material"
            elif is_fifty:
                draw_reason = "50-Move Rule"
            elif is_rep:
                draw_reason = "Threefold Repetition"

        result = MoveResult(
            success=True,
            move=move,
            san=san,
            from_square=from_square,
            to_square=to_square,
            piece_moved=piece,
            captured_piece=captured_piece,
            is_capture=is_capture,
            is_castling=is_castling,
            is_en_passant=is_en_passant,
            is_promotion=is_promo,
            promotion_piece_type=promo_type,
            is_check=is_check,
            is_checkmate=is_checkmate,
            is_stalemate=is_stalemate,
            is_insufficient_material=is_insufficient,
            is_fifty_moves=is_fifty,
            is_repetition=is_rep,
            is_draw=is_draw,
            draw_reason=draw_reason,
        )

        self.move_history.append(result)

        # Trigger hooks
        self.mode.on_move_executed(self, result)
        for hook in self._post_move_hooks:
            hook(self, result)
        self.mode.on_turn_change(self)

        return result

    def undo_move(self) -> Optional[MoveResult]:
        """Undo the most recent move, reverting the authoritative board state."""
        if not self.move_history or len(self.board.move_stack) == 0:
            return None

        last_res = self.move_history.pop()
        self.board.pop()

        # Remove captured piece if any
        if last_res.captured_piece:
            capturing_color = "w" if last_res.piece_moved.color == chess.WHITE else "b"
            captured_code = piece_to_code(last_res.captured_piece)
            if captured_code and captured_code in self.captured_pieces[capturing_color]:
                self.captured_pieces[capturing_color].remove(captured_code)

        if self.move_history:
            prev = self.move_history[-1]
            self.last_move = (prev.from_square, prev.to_square)
        else:
            self.last_move = None

        return last_res

    def reset(self, fen: Optional[str] = None) -> None:
        """Reset the game to the initial starting position or a custom FEN."""
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_history.clear()
        self.captured_pieces = {"w": [], "b": []}
        self.last_move = None
        self.timeout_winner = None
        self.timeout_reason = None
        self.mode.on_init(self)

    # -------------------------------------------------------------------------
    # Mod Extension Hooks
    # -------------------------------------------------------------------------

    def register_pre_move_validator(self, validator: Callable[["GameState", chess.Move], bool]) -> None:
        """Register a callback that can block a move."""
        self._pre_move_validators.append(validator)

    def register_post_move_hook(self, hook: Callable[["GameState", MoveResult], None]) -> None:
        """Register a callback executed after each valid move."""
        self._post_move_hooks.append(hook)

    # -------------------------------------------------------------------------
    # Matrix & FEN Compatibility
    # -------------------------------------------------------------------------

    def to_matrix(self, flipped: bool = False) -> List[List[Optional[str]]]:
        """
        Generate an 8x8 matrix representing piece codes as rendered on screen.
        matrix[row][col] matches row 0 (top) down to row 7 (bottom).
        """
        matrix: List[List[Optional[str]]] = []
        for row in range(8):
            row_items: List[Optional[str]] = []
            for col in range(8):
                sq = board_coords_to_square(row, col, flipped=flipped)
                piece = self.board.piece_at(sq)
                row_items.append(piece_to_code(piece))
            matrix.append(row_items)
        return matrix

    def to_fen(self) -> str:
        """Export board state to FEN string for multiplayer or serialization."""
        return self.board.fen()

    def load_fen(self, fen: str) -> None:
        """Load state from FEN string."""
        self.reset(fen=fen)
