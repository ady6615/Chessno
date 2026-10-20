# snail_engine.py
"""
Immortal Snail Game Mode for Chessno.

Rules:
1. Two immortal snails are present on the chessboard—one for each team:
   - White Snail belongs to White and relentlessly hunts the Black King.
   - Black Snail belongs to Black and relentlessly hunts the White King.
2. The snails advance one tile after every five completed legal chess piece moves,
   counted across both players.
3. Invalid or rejected moves do not count towards the five-move threshold.
4. Each snail step moves it closer to its designated target king.
5. Snails recalculate their direction using the target king's current position on each step.
6. Friendly piece protection & detour navigation:
   - A snail CANNOT defeat or step onto pieces belonging to its own team.
   - If obstructed by a friendly piece, it takes a detour (longer route) around it.
7. Hostile piece squashing:
   - If a snail steps onto an opposing non-king piece, that piece is crushed and removed.
8. Instant victory:
   - If a snail steps onto the opposing king's square, the opposing king is captured immediately
     and that snail's team wins the game.
9. Absolute immunity:
   - Snails cannot be captured, removed, blocked, or pushed away by chess pieces.
   - No piece may capture a snail, including kings (pieces cannot move onto a snail's square).
   - Snails cannot capture or crush each other.
10. Off-board entry:
    - Snails begin at distinct off-board entry points and step onto the board on their first scheduled step.
"""

from collections import deque
from typing import Optional, Tuple, List, Dict, Any, Union
import chess

from game_engine import GameMode, GameState, MoveResult
from coordinates import piece_to_code


class SnailEntity:
    """
    State and pathfinding logic for an individual Immortal Snail.
    """

    def __init__(
        self,
        team_color: chess.Color,
        spawn_pos: Optional[Union[Tuple[int, int], chess.Square]] = None,
    ):
        self.team_color: chess.Color = team_color
        self.target_color: chess.Color = chess.BLACK if team_color == chess.WHITE else chess.WHITE

        if spawn_pos is None:
            # White enters from the left flank (outside a3), Black from right flank (outside h6)
            self.spawn_pos: Tuple[int, int] = (-1, 2) if team_color == chess.WHITE else (8, 5)
        elif isinstance(spawn_pos, int):
            self.spawn_pos = (chess.square_file(spawn_pos), chess.square_rank(spawn_pos))
        else:
            self.spawn_pos = (int(spawn_pos[0]), int(spawn_pos[1]))

        self.current_pos: Tuple[int, int] = self.spawn_pos
        self.previous_pos: Optional[Tuple[int, int]] = None
        self.is_on_board: bool = (0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7)
        self.steps_taken: int = 0
        self.trail: List[Tuple[int, int]] = [self.current_pos] if self.is_on_board else []
        self.crushed_pieces: List[str] = []
        self.target_caught: bool = False
        self.status_message: str = f"{self.team_name} Snail lurking"

    @property
    def team_name(self) -> str:
        return "White" if self.team_color == chess.WHITE else "Black"

    @property
    def target_name(self) -> str:
        return "Black" if self.team_color == chess.WHITE else "White"

    @property
    def square(self) -> Optional[chess.Square]:
        """Return chess.Square if snail is on the 8x8 board, else None."""
        if self.is_on_board and 0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7:
            return chess.square(self.current_pos[0], self.current_pos[1])
        return None

    @property
    def location_name(self) -> str:
        """Formatted human-readable location of the snail."""
        sq = self.square
        if sq is not None:
            return chess.square_name(sq).upper()
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

    def reset(self) -> None:
        """Reset snail to its initial spawn point."""
        self.current_pos = self.spawn_pos
        self.previous_pos = None
        self.is_on_board = (0 <= self.current_pos[0] <= 7 and 0 <= self.current_pos[1] <= 7)
        self.steps_taken = 0
        self.trail = [self.current_pos] if self.is_on_board else []
        self.crushed_pieces.clear()
        self.target_caught = False
        self.status_message = f"{self.team_name} Snail hunting {self.target_name} King"

    def compute_next_step(
        self,
        game_state: GameState,
        other_snail_pos: Optional[Tuple[int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Compute the next adjacent coordinate for this snail using BFS detour pathfinding.

        Rules:
        - Must NOT step onto friendly pieces (pieces of self.team_color).
        - Must NOT step onto the non-target king (friendly king).
        - Must NOT step onto the other snail.
        - CAN step onto enemy pieces (crushing them).
        - CAN step onto target king (capturing it).
        - BFS computes shortest unblocked path to target king, routing AROUND friendly pieces.
        - Deterministic tie-breakers: BFS distance, Euclidean distance, Chebyshev distance, file, rank.
        """
        target_sq = game_state.king_square(self.target_color)
        if target_sq is None:
            return None

        tx = chess.square_file(target_sq)
        ty = chess.square_rank(target_sq)

        cx, cy = self.current_pos
        if (cx, cy) == (tx, ty):
            return (tx, ty)

        # 1. Run BFS backwards from target king to compute shortest unblocked distances
        dist: Dict[Tuple[int, int], int] = {(tx, ty): 0}
        queue = deque([(tx, ty, 0)])

        def is_walkable(x: int, y: int) -> bool:
            """Determine if square (x, y) can be traversed by this snail."""
            if not (0 <= x <= 7 and 0 <= y <= 7):
                return False
            sq = chess.square(x, y)
            if sq == target_sq:
                return True
            # Friendly piece obstructs!
            p = game_state.board.piece_at(sq)
            if p is not None:
                if p.color == self.team_color:
                    return False
                if p.piece_type == chess.KING:
                    return False
            # Other snail obstructs
            if other_snail_pos is not None and (x, y) == other_snail_pos:
                return False
            return True

        while queue:
            x, y, d = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx <= 7 and 0 <= ny <= 7 and (nx, ny) not in dist:
                        if is_walkable(nx, ny):
                            dist[(nx, ny)] = d + 1
                            queue.append((nx, ny, d + 1))

        # 2. Evaluate adjacent neighbors from current position
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx <= 7 and 0 <= ny <= 7):
                    continue
                if not is_walkable(nx, ny):
                    continue

                d_val = dist.get((nx, ny), 9999)
                euclid = (nx - tx) ** 2 + (ny - ty) ** 2
                cheb = max(abs(nx - tx), abs(ny - ty))
                candidates.append((d_val, euclid, cheb, nx, ny))

        if not candidates:
            # Fallback if completely hemmed in: pick any neighbor minimizing distance to target
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx <= 7 and 0 <= ny <= 7:
                        # At minimum, never crush own king or other snail
                        sq = chess.square(nx, ny)
                        p = game_state.board.piece_at(sq)
                        if p is not None and p.piece_type == chess.KING and sq != target_sq:
                            continue
                        if other_snail_pos is not None and (nx, ny) == other_snail_pos:
                            continue
                        euclid = (nx - tx) ** 2 + (ny - ty) ** 2
                        cheb = max(abs(nx - tx), abs(ny - ty))
                        candidates.append((9999, euclid, cheb, nx, ny))

        if not candidates:
            return None

        # Sort deterministically
        candidates.sort(key=lambda c: (c[0], c[1], c[2], c[3], c[4]))
        best = candidates[0]
        return (best[3], best[4])

    def step(
        self,
        game_state: GameState,
        other_snail_pos: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Advance this snail one tile towards the opposing king."""
        target_sq = game_state.king_square(self.target_color)
        if target_sq is None:
            return

        next_coords = self.compute_next_step(game_state, other_snail_pos=other_snail_pos)
        if next_coords is None:
            return

        nx, ny = next_coords
        dest_sq = chess.square(nx, ny)

        self.previous_pos = self.current_pos
        self.current_pos = (nx, ny)
        self.is_on_board = True
        self.steps_taken += 1
        self.trail.append((nx, ny))

        # Check if target king was reached
        if dest_sq == target_sq:
            self.target_caught = True
            self.status_message = f"{self.team_name} Snail CAUGHT {self.target_name} King!"
            try:
                import Assets
                Assets.play_sound("game_over")
            except Exception:
                pass
            return

        # Check if enemy non-king piece occupies destination
        piece = game_state.board.piece_at(dest_sq)
        if piece is not None:
            if piece.color != self.team_color and piece.piece_type != chess.KING:
                removed = game_state.board.remove_piece_at(dest_sq)
                if removed:
                    code = piece_to_code(removed)
                    if code:
                        self.crushed_pieces.append(code)
                        side_key = "w" if self.team_color == chess.WHITE else "b"
                        game_state.captured_pieces[side_key].append(code)
                    self.status_message = f"{self.team_name} Snail crushed {removed.symbol()} on {chess.square_name(dest_sq).upper()}!"
                    try:
                        import Assets
                        Assets.play_sound("capture")
                    except Exception:
                        pass
        else:
            self.status_message = f"{self.team_name} Snail moved to {chess.square_name(dest_sq).upper()}"
            try:
                import Assets
                Assets.play_sound("move")
            except Exception:
                pass


class ImmortalSnailMode(GameMode):
    """
    Authoritative Game Mode for Immortal Snail (Dual-Snail Edition).
    """

    MOVES_PER_STEP: int = 5

    def __init__(
        self,
        white_spawn_pos: Optional[Union[Tuple[int, int], chess.Square]] = None,
        black_spawn_pos: Optional[Union[Tuple[int, int], chess.Square]] = None,
        target_color: Optional[chess.Color] = None,
        spawn_pos: Optional[Union[Tuple[int, int], chess.Square]] = None,
    ):
        super().__init__(name="Immortal Snail")

        # Backward compatibility with single-snail constructor calls
        if target_color is not None and spawn_pos is not None:
            if target_color == chess.BLACK:
                white_spawn_pos = spawn_pos
            else:
                black_spawn_pos = spawn_pos

        self.white_snail = SnailEntity(team_color=chess.WHITE, spawn_pos=white_spawn_pos)
        self.black_snail = SnailEntity(team_color=chess.BLACK, spawn_pos=black_spawn_pos)
        self.snails: List[SnailEntity] = [self.white_snail, self.black_snail]

        self.moves_until_next_step: int = self.MOVES_PER_STEP
        self.total_legal_moves: int = 0
        self.status_message: str = "Immortal Snails active on both sides!"

    # -------------------------------------------------------------------------
    # Backward Compatibility Properties
    # -------------------------------------------------------------------------

    @property
    def target_color(self) -> chess.Color:
        return self.white_snail.target_color

    @property
    def target_name(self) -> str:
        return self.white_snail.target_name

    @property
    def opponent_name(self) -> str:
        return self.white_snail.team_name

    @property
    def spawn_pos(self) -> Tuple[int, int]:
        return self.white_snail.spawn_pos

    @spawn_pos.setter
    def spawn_pos(self, pos: Tuple[int, int]) -> None:
        self.white_snail.spawn_pos = pos

    @property
    def current_pos(self) -> Tuple[int, int]:
        return self.white_snail.current_pos

    @property
    def is_on_board(self) -> bool:
        return self.white_snail.is_on_board or self.black_snail.is_on_board

    @property
    def square(self) -> Optional[chess.Square]:
        return self.white_snail.square

    @property
    def steps_taken(self) -> int:
        return max(self.white_snail.steps_taken, self.black_snail.steps_taken)

    @property
    def crushed_pieces(self) -> List[str]:
        return self.white_snail.crushed_pieces + self.black_snail.crushed_pieces

    @property
    def trail(self) -> List[Tuple[int, int]]:
        return self.white_snail.trail

    @property
    def target_caught(self) -> bool:
        return self.white_snail.target_caught or self.black_snail.target_caught

    @property
    def location_name(self) -> str:
        return f"W: {self.white_snail.location_name} | B: {self.black_snail.location_name}"

    def distance_to_target(self, game_state: GameState) -> Optional[int]:
        return self.white_snail.distance_to_target(game_state)

    def set_target_color(self, color: chess.Color) -> bool:
        """Preserved for backward compatibility."""
        return True

    # -------------------------------------------------------------------------
    # Game Mode Lifecycle & Hooks
    # -------------------------------------------------------------------------

    def on_init(self, game_state: GameState) -> None:
        """Reset snails to initial spawn points and move counter to 5."""
        self.white_snail.reset()
        self.black_snail.reset()
        self.moves_until_next_step = self.MOVES_PER_STEP
        self.total_legal_moves = 0
        self.status_message = "Immortal Snails active on both sides!"

    def can_move(self, game_state: GameState, move: chess.Move) -> bool:
        """
        Rule: Neither snail can be captured or landed on by any chess piece,
        including kings.
        """
        for snail in self.snails:
            if snail.is_on_board and snail.square is not None:
                if move.to_square == snail.square:
                    return False
        return True

    def on_move_executed(self, game_state: GameState, move_result: MoveResult) -> None:
        """
        Called after every legal move committed to the board.
        Advances both snails after precisely five completed legal moves.
        """
        if not move_result.success:
            return
        if self.is_game_over(game_state):
            return

        self.total_legal_moves += 1
        self.moves_until_next_step -= 1

        if self.moves_until_next_step <= 0:
            self.step_both_snails(game_state)
            self.moves_until_next_step = self.MOVES_PER_STEP

    def step_both_snails(self, game_state: GameState) -> None:
        """Step White Snail and Black Snail towards their respective target kings."""
        self.white_snail.step(game_state, other_snail_pos=self.black_snail.current_pos)
        self.black_snail.step(game_state, other_snail_pos=self.white_snail.current_pos)

    def step_snail(self, game_state: GameState) -> None:
        """Backward compatibility convenience method."""
        self.step_both_snails(game_state)

    def is_game_over(self, game_state: GameState) -> bool:
        """Game is over if either snail has captured the opposing king."""
        return self.white_snail.target_caught or self.black_snail.target_caught

    def winner(self, game_state: GameState) -> Optional[chess.Color]:
        """Victor determined by which snail successfully caught the opposing king."""
        if self.white_snail.target_caught and not self.black_snail.target_caught:
            return chess.WHITE
        if self.black_snail.target_caught and not self.white_snail.target_caught:
            return chess.BLACK
        return None

    def game_over_reason(self, game_state: GameState) -> Optional[str]:
        if self.white_snail.target_caught:
            return "White's Immortal Snail caught the Black King! White wins!"
        if self.black_snail.target_caught:
            return "Black's Immortal Snail caught the White King! Black wins!"
        return None

    def get_overlay_entities(self, game_state: GameState) -> List[Dict[str, Any]]:
        """Return metadata for both snails for rendering."""
        return [
            {
                "type": "immortal_snail",
                "team_color": s.team_color,
                "target_color": s.target_color,
                "pos": s.current_pos,
                "is_on_board": s.is_on_board,
                "steps_taken": s.steps_taken,
                "trail": s.trail,
                "caught": s.target_caught,
            }
            for s in self.snails
        ]
