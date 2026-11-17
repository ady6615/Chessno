# crazyhouse_engine.py
"""
Crazyhouse Game Mode for Chessno.

Rules of Crazyhouse:
- Standard starting board layout and standard movement rules.
- Captured pieces enter the capturing player's reserve pocket.
- The captured piece takes the capturing player's color.
- On any turn, a player may either make a regular board move OR "drop" any piece
  from their reserve pocket onto any vacant square on the board.
- Pawns cannot be dropped onto the 1st or 8th rank.
- Dropping a piece must adhere to standard check rules (cannot drop into self-check).
- Promoted pawns revert back to pawns when captured.
- First to checkmate the opponent wins.
"""

from typing import Optional, List, Dict
import chess
import chess.variant

from game_engine import GameMode, GameState, MoveResult


CRAZYHOUSE_PIECE_ORDER = [
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
]

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
}


class CrazyhouseMode(GameMode):
    """
    Implements Crazyhouse variant using python-chess CrazyhouseBoard.
    """

    def __init__(self):
        super().__init__(name="Crazyhouse")
        self.selected_drop_piece: Optional[int] = None

    def on_init(self, game_state: GameState) -> None:
        """Initialize or reset the board to a fresh CrazyhouseBoard."""
        game_state.board = chess.variant.CrazyhouseBoard()
        self.selected_drop_piece = None
        self.sync_captured_pieces(game_state)

    def sync_captured_pieces(self, game_state: GameState) -> None:
        """
        Synchronize game_state.captured_pieces to reflect the current pocket reserve pieces.
        White's pocket pieces are White pieces ('wP', 'wN', etc.).
        Black's pocket pieces are Black pieces ('bP', 'bN', etc.).
        """
        if not hasattr(game_state.board, "pockets"):
            return

        w_pocket = game_state.board.pockets[chess.WHITE]
        b_pocket = game_state.board.pockets[chess.BLACK]

        w_list = []
        for pt in CRAZYHOUSE_PIECE_ORDER:
            cnt = w_pocket.count(pt)
            sym = chess.piece_symbol(pt).upper()
            w_list.extend([f"w{sym}"] * cnt)

        b_list = []
        for pt in CRAZYHOUSE_PIECE_ORDER:
            cnt = b_pocket.count(pt)
            sym = chess.piece_symbol(pt).upper()
            b_list.extend([f"b{sym}"] * cnt)

        game_state.captured_pieces["w"] = w_list
        game_state.captured_pieces["b"] = b_list

    def on_turn_change(self, game_state: GameState) -> None:
        """Called when turn changes: deselect drop piece and sync pocket reserves."""
        self.selected_drop_piece = None
        self.sync_captured_pieces(game_state)

    def on_move_executed(self, game_state: GameState, result: MoveResult) -> None:
        """Called after any move execution: ensure reserve pocket synchronization."""
        self.sync_captured_pieces(game_state)

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """All standard and drop moves permitted by CrazyhouseBoard are valid."""
        return True

    def get_pocket_counts(self, game_state: GameState, color: chess.Color) -> Dict[int, int]:
        """Return a mapping of piece_type -> count in reserve pocket for given color."""
        if not hasattr(game_state.board, "pockets"):
            return {pt: 0 for pt in CRAZYHOUSE_PIECE_ORDER}
        pocket = game_state.board.pockets[color]
        return {pt: pocket.count(pt) for pt in CRAZYHOUSE_PIECE_ORDER}

    def get_legal_drops(self, game_state: GameState, piece_type: int) -> List[chess.Square]:
        """
        Return list of squares where dropping `piece_type` is legal for the current player.
        """
        if not hasattr(game_state.board, "pockets"):
            return []
        
        pocket = game_state.board.pockets[game_state.turn]
        if pocket.count(piece_type) <= 0:
            return []

        legal_drops: List[chess.Square] = []
        for m in game_state.board.legal_moves:
            if m.drop == piece_type:
                legal_drops.append(m.to_square)
        return legal_drops

    def is_legal_drop(
        self,
        game_state: GameState,
        to_square: chess.Square,
        piece_type: int,
    ) -> bool:
        """Check if dropping `piece_type` onto `to_square` is legal."""
        move = chess.Move(to_square, to_square, drop=piece_type)
        return move in game_state.board.legal_moves

    def get_status_message(self, game_state: GameState) -> Optional[str]:
        """Status text displayed in panel."""
        if game_state.is_game_over():
            return None
        if game_state.is_in_check():
            return f"{game_state.turn_name} is in Check!"

        if hasattr(game_state.board, "pockets"):
            cur_pocket = game_state.board.pockets[game_state.turn]
            count = len(cur_pocket)
            if count > 0:
                return f"{game_state.turn_name}'s Turn • {count} in reserve"

        return f"{game_state.turn_name}'s Turn"
