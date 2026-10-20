# snail_engine.py
"""
Immortal Snail Game Mode for Chessno.

Rules:
1. The immortal snail advances one tile after every three completed legal chess piece moves,
   counted across both players.
2. Invalid or rejected moves do not count towards the three-move threshold.
3. Each snail step moves it closer to its designated target king (White or Black).
4. The snail recalculates its direction using the target king's current position whenever it moves.
5. It cannot be captured, removed, blocked, or pushed away by chess pieces.
6. The snail is not a normal chess piece and cannot be selected or moved by a player.
7. The snail ignores ordinary piece occupancy when choosing its route.
8. If the snail steps onto a square occupied by a non-king piece, that piece is removed from the board.
9. If the snail steps onto its target king's square, the target king is captured immediately and
   that side loses the game.
10. No piece may capture the snail, including the king (pieces cannot move onto the snail's square).
11. The target king is configurable at game start (White or Black) and fixed for the duration of the match.
12. The snail begins at a designated off-board entry point, entering the board on its first scheduled step.
"""

from typing import Optional, Tuple, List, Dict, Any, Union
import chess

from game_engine import GameMode, GameState, MoveResult
from coordinates import piece_to_code


class ImmortalSnailMode(GameMode):
    """
    Authoritative state and logic for Immortal Snail Mode.
    """

    def __init__(
        self,
        target_color: chess.Color = chess.BLACK,
        spawn_pos: Optional[Union[Tuple[int, int], chess.Square]] = None,
    ):
        super().__init__(name="Immortal Snail")
        self.target_color: chess.Color = target_color

        # If spawn_pos is None, spawn off the board edge opposite the target king
        if spawn_pos is None:
            self.spawn_pos: Tuple[int, int] = (0, 8) if target_color == chess.WHITE else (0, -1)
        elif isinstance(spawn_pos, int):
            self.spawn_pos = (chess.square_file(spawn_pos), chess.square_rank(spawn_pos))
        else:
            self.spawn_pos = (int(spawn_pos[0]), int(spawn_pos[1]))

        self.current_pos: Tuple[int, int] = self.spawn_pos
        self.previous_pos: Optional[Tuple[int, int]] = None
        self.is_on_board: bool = (0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7)
        self.moves_until_next_step: int = 3
        self.total_legal_moves: int = 0
        self.steps_taken: int = 0
        self.trail: List[Tuple[int, int]] = [self.current_pos] if self.is_on_board else []
        self.crushed_pieces: List[str] = []
        self.target_caught: bool = False
        self.status_message: str = f"Immortal Snail targeting {self.target_name} King"

    @property
    def target_name(self) -> str:
        return "White" if self.target_color == chess.WHITE else "Black"

    @property
    def opponent_name(self) -> str:
        return "Black" if self.target_color == chess.WHITE else "White"

    @property
    def square(self) -> Optional[chess.Square]:
        """Return the chess.Square of the snail if on the 8x8 board, else None."""
        if self.is_on_board and 0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7:
            return chess.square(self.current_pos[0], self.current_pos[1])
        return None

    @property
    def location_name(self) -> str:
        """Formatted human-readable location of the snail."""
        sq = self.square
        if sq is not None:
            return chess.square_name(sq).upper()
        # Off-board formatting
        f, r = self.current_pos
        file_char = chr(ord('a') + f) if 0 <= f <= 7 else f"{f}"
        rank_num = r + 1
        return f"Off-board ({file_char}{rank_num})"

    def distance_to_target(self, game_state: GameState) -> Optional[int]:
        """Chebyshev distance from snail to target king."""
        target_sq = game_state.king_square(self.target_color)
        if target_sq is None:
            return None
        tx = chess.square_file(target_sq)
        ty = chess.square_rank(target_sq)
        cx, cy = self.current_pos
        return max(abs(cx - tx), abs(cy - ty))

    def set_target_color(self, color: chess.Color) -> bool:
        """
        Configure target king before any legal moves have been executed.
        Returns True if changed, False if locked after game start.
        """
        if self.total_legal_moves > 0:
            return False
        self.target_color = color
        if not self.is_on_board and self.steps_taken == 0:
            self.spawn_pos = (0, 8) if color == chess.WHITE else (0, -1)
            self.current_pos = self.spawn_pos
        self.status_message = f"Target set to {self.target_name} King"
        return True

    def on_init(self, game_state: GameState) -> None:
        """Initialize or reset Immortal Snail Mode."""
        self.current_pos = self.spawn_pos
        self.previous_pos = None
        self.is_on_board = (0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7)
        self.moves_until_next_step = 3
        self.total_legal_moves = 0
        self.steps_taken = 0
        self.trail = [self.current_pos] if self.is_on_board else []
        self.crushed_pieces.clear()
        self.target_caught = False
        self.status_message = f"Immortal Snail targeting {self.target_name} King"

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """
        Rule: No piece may capture the snail, including the king.
        Pieces cannot move to the square occupied by the snail.
        """
        if self.is_on_board and self.square is not None:
            if move.to_square == self.square:
                return False
        return True

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """
        Called immediately after a move is committed to the board.
        Advances snail every 3 completed legal chess piece moves.
        """
        if not move_result.success:
            return
        if self.target_caught:
            return

        self.total_legal_moves += 1
        self.moves_until_next_step -= 1

        if self.moves_until_next_step <= 0:
            self.step_snail(game_state)
            self.moves_until_next_step = 3

    def compute_next_step(self, game_state: GameState) -> Optional[Tuple[int, int]]:
        """
        Calculate the next adjacent coordinate for the snail.

        Rules:
        - Target: designated target king's current square.
        - Step: 1 tile in any of 8 directions (horizontal, vertical, diagonal).
        - Must be a square on the 8x8 board.
        - Must reduce distance to the target king.
        - Cannot step onto the non-target king.
        - Tie-breaker:
            1. Lowest Chebyshev distance (max(|dx|, |dy|))
            2. Lowest Euclidean distance squared ((dx)^2 + (dy)^2)
            3. Deterministic coordinate ordering: file ascending, then rank ascending.
        """
        target_sq = game_state.king_square(self.target_color)
        if target_sq is None:
            return None

        tx = chess.square_file(target_sq)
        ty = chess.square_rank(target_sq)

        opp_color = chess.BLACK if self.target_color == chess.WHITE else chess.WHITE
        opp_king_sq = game_state.king_square(opp_color)
        opp_coords = (chess.square_file(opp_king_sq), chess.square_rank(opp_king_sq)) if opp_king_sq is not None else None

        cx, cy = self.current_pos

        if (cx, cy) == (tx, ty):
            return (tx, ty)

        curr_cheb = max(abs(cx - tx), abs(cy - ty))
        curr_euclid = (cx - tx) ** 2 + (cy - ty) ** 2

        candidates = []

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cx + dx, cy + dy
                # Destination must be on the 8x8 chessboard
                if not (0 <= nx <= 7 and 0 <= ny <= 7):
                    continue
                # Cannot step onto the opposing (non-target) king
                if opp_coords is not None and (nx, ny) == opp_coords:
                    continue

                cheb = max(abs(nx - tx), abs(ny - ty))
                euclid = (nx - tx) ** 2 + (ny - ty) ** 2

                # If off-board, any on-board neighbor entering the board towards the target is valid
                if not self.is_on_board:
                    candidates.append((cheb, euclid, nx, ny))
                else:
                    # On board: candidate must reduce distance to target king
                    if cheb < curr_cheb or (cheb == curr_cheb and euclid < curr_euclid):
                        candidates.append((cheb, euclid, nx, ny))

        # Fallback if strict reduction yielded no candidates (e.g. blocked or cornered)
        if not candidates:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx <= 7 and 0 <= ny <= 7:
                        if opp_coords is not None and (nx, ny) == opp_coords:
                            continue
                        cheb = max(abs(nx - tx), abs(ny - ty))
                        euclid = (nx - tx) ** 2 + (ny - ty) ** 2
                        candidates.append((cheb, euclid, nx, ny))

        if not candidates:
            return None

        # Sort deterministically
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        best = candidates[0]
        return (best[2], best[3])

    def step_snail(self, game_state: GameState) -> None:
        """
        Advance the snail by one tile towards the target king.
        Handles non-king piece squashing and target king capture.
        """
        target_sq = game_state.king_square(self.target_color)
        if target_sq is None:
            return

        next_coords = self.compute_next_step(game_state)
        if next_coords is None:
            return

        nx, ny = next_coords
        dest_sq = chess.square(nx, ny)

        self.previous_pos = self.current_pos
        self.current_pos = (nx, ny)
        self.is_on_board = True
        self.steps_taken += 1
        self.trail.append((nx, ny))

        # Check if target king is on destination square
        if dest_sq == target_sq:
            self.target_caught = True
            self.status_message = f"Immortal Snail CAUGHT the {self.target_name} King!"
            try:
                import Assets
                Assets.play_sound("game_over")
            except Exception:
                pass
            return

        # Check if non-king piece occupies destination square
        piece = game_state.board.piece_at(dest_sq)
        if piece is not None and piece.piece_type != chess.KING:
            removed = game_state.board.remove_piece_at(dest_sq)
            if removed:
                code = piece_to_code(removed)
                if code:
                    self.crushed_pieces.append(code)
                    capturing_side = "b" if self.target_color == chess.WHITE else "w"
                    game_state.captured_pieces[capturing_side].append(code)
                self.status_message = f"Snail crushed {removed.symbol()} on {chess.square_name(dest_sq).upper()}!"
                try:
                    import Assets
                    Assets.play_sound("capture")
                except Exception:
                    pass
        else:
            self.status_message = f"Snail crawled to {chess.square_name(dest_sq).upper()}"
            try:
                import Assets
                Assets.play_sound("move")
            except Exception:
                pass

    def is_game_over(self, game_state: GameState) -> bool:
        """Return True if the snail has captured its target king."""
        return self.target_caught

    def winner(self, game_state: GameState) -> Optional[chess.Color]:
        """Opponent of target king wins when target king is caught."""
        if self.target_caught:
            return chess.BLACK if self.target_color == chess.WHITE else chess.WHITE
        return None

    def game_over_reason(self, game_state: GameState) -> Optional[str]:
        """Detailed game over reason if target king is caught."""
        if self.target_caught:
            return f"Immortal Snail caught {self.target_name} King! {self.opponent_name} wins!"
        return None

    def get_overlay_entities(self, game_state: GameState) -> List[Dict[str, Any]]:
        """Return snail entity metadata for renderer."""
        return [
            {
                "type": "immortal_snail",
                "pos": self.current_pos,
                "is_on_board": self.is_on_board,
                "target_color": self.target_color,
                "steps_taken": self.steps_taken,
                "moves_until_next_step": self.moves_until_next_step,
                "trail": self.trail,
                "caught": self.target_caught,
            }
        ]
