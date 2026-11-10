# renderer.py
"""
Rendering system for Chessno.

Handles all Pygame drawing routines:
- Chessboard drawing with configurable origin and size
- Highlighting: selected piece, legal destinations (move vs capture), last move, king in check
- Centered piece rendering derived strictly from authoritative GameState
- Drag-and-drop piece rendering
- In-game Pawn Promotion dialog overlay
- Start Menu & Game Mode Selection modal
- Right-side information panel with theme switcher, controls, and animated UNO card display
"""

import math
from typing import Optional, Tuple, List, Dict, Any
import pygame
import chess

from coordinates import (
    BOARD_X,
    BOARD_Y,
    SQUARE_SIZE,
    square_to_rect,
    square_to_piece_center,
    square_to_board_coords,
    piece_to_code,
)
from game_engine import GameState
from snail_engine import ImmortalSnailMode
from timer import ChessTimer
from ai_bot import BotDifficulty, BOT_DIFFICULTY_METADATA, ChessBotController

# Theme and UI Color Palette (Modern Slate & Obsidian Dark Theme)
BG_COLOR = (18, 20, 26)
PANEL_BG = (25, 28, 36)
PANEL_CARD_BG = (34, 38, 48)
PANEL_BORDER = (48, 54, 70)
TEXT_PRIMARY = (248, 249, 252)
TEXT_SECONDARY = (168, 176, 194)
TEXT_MUTED = (118, 126, 142)
ACCENT_COLOR = (60, 205, 145)       # Mint emerald
ACCENT_HOVER = (80, 225, 165)
CHECK_COLOR = (239, 68, 68)         # Alert crimson
CHECK_HOVER = (248, 113, 113)
GOLD_COLOR = (251, 191, 36)         # Trophy gold
CYAN_COLOR = (56, 189, 248)         # Cyan highlight
BTN_COLOR = (42, 47, 60)
BTN_HOVER = (58, 65, 82)
BTN_BORDER = (65, 73, 92)

# UNO Card Colors
UNO_COLORS = {
    "Red": (220, 48, 48),
    "Blue": (35, 115, 230),
    "Green": (42, 175, 80),
    "Yellow": (235, 190, 25),
}


class UIButtons:
    """Stores bounding rectangles for clickable panel buttons."""
    def __init__(self, panel_x: int, panel_width: int):
        self.panel_x = panel_x
        self.panel_width = panel_width
        
        # Mode, Timer, Bot quick toggle, and Fullscreen selector buttons in header
        self.bot_quick_toggle = pygame.Rect(panel_x, 28, 120, 26)
        self.fullscreen = pygame.Rect(panel_x + panel_width - 86, 28, 86, 26)
        self.mode_select = pygame.Rect(panel_x + panel_width - 176, 64, 76, 26)
        self.timer_select = pygame.Rect(panel_x + panel_width - 94, 64, 94, 26)

        # Chess Clocks
        clock_w = (panel_width - 8) // 2
        self.white_clock = pygame.Rect(panel_x, 100, clock_w, 46)
        self.black_clock = pygame.Rect(panel_x + clock_w + 8, 100, clock_w, 46)

        # Theme switching buttons
        self.prev_theme = pygame.Rect(panel_x, 328, 65, 30)
        self.next_theme = pygame.Rect(panel_x + panel_width - 65, 328, 65, 30)
        
        # Action buttons
        self.new_game = pygame.Rect(panel_x, 364, panel_width, 30)
        self.flip_board = pygame.Rect(panel_x, 398, (panel_width - 10) // 2, 28)
        self.sound_toggle = pygame.Rect(panel_x + (panel_width - 10) // 2 + 10, 398, (panel_width - 10) // 2, 28)

        # AI Bot Control Buttons
        btn_bot_w = (panel_width - 8) // 2
        self.bot_toggle = pygame.Rect(panel_x, 430, btn_bot_w, 28)
        self.bot_difficulty = pygame.Rect(panel_x + btn_bot_w + 8, 430, btn_bot_w, 28)

        # UNO Interactive Buttons
        self.draw_card = pygame.Rect(panel_x + 14, 644, panel_width - 28, 38)
        self.deck_card = pygame.Rect(panel_x + (panel_width - 105) // 2, 482, 105, 145)

        # Immortal Snail Target Selection Buttons
        btn_w = (panel_width - 34) // 2
        self.target_white = pygame.Rect(panel_x + 14, 510, btn_w, 28)
        self.target_black = pygame.Rect(panel_x + 14 + btn_w + 6, 510, btn_w, 28)


class GameStartBounceAnimation:
    """
    Manages a staggered, multi-bounce spring animation for chess pieces at the start of a new game.
    Simulates a natural parabolic bounce under gravity with decreasing rebound height and dynamic ground shadows.
    """
    def __init__(
        self,
        piece_duration: float = 0.50,
        max_height: float = 38.0,
        stagger_col: float = 0.025,
        stagger_pawn: float = 0.04,
    ):
        self.piece_duration = piece_duration
        self.max_height = max_height
        self.stagger_col = stagger_col
        self.stagger_pawn = stagger_pawn
        self.total_duration = 7 * stagger_col + stagger_pawn + piece_duration
        self.elapsed: float = 0.0
        self.active: bool = False

    def trigger(self) -> None:
        """Start or restart the game-start bounce animation."""
        self.elapsed = 0.0
        self.active = True

    def update(self, dt: float) -> None:
        """Advance animation time by dt seconds."""
        if not self.active:
            return
        self.elapsed += max(0.0, dt)
        if self.elapsed >= self.total_duration:
            self.active = False

    def cancel(self) -> None:
        """Immediately stop and dismiss the bounce animation."""
        self.active = False
        self.elapsed = 0.0

    @property
    def is_active(self) -> bool:
        return self.active

    def get_offset(self, col: int, is_pawn: bool) -> Tuple[float, float]:
        """
        Calculate the vertical pixel offset (negative is upward) and ground shadow scale.
        Returns: (y_offset, shadow_scale)
        """
        if not self.active:
            return 0.0, 1.0

        delay = col * self.stagger_col + (self.stagger_pawn if is_pawn else 0.0)
        t = self.elapsed - delay
        if t < 0.0 or t >= self.piece_duration:
            return 0.0, 1.0

        # Two-stage physics bounce:
        # Stage 1 (0 to 65% duration): Major leap under gravity
        # Stage 2 (65% to 100% duration): Secondary rebound
        t1 = self.piece_duration * 0.65
        t2 = self.piece_duration - t1
        h1 = self.max_height
        h2 = self.max_height * 0.28

        if t < t1:
            p = t / t1
            h = 4.0 * h1 * p * (1.0 - p)
        else:
            p = (t - t1) / t2
            h = 4.0 * h2 * p * (1.0 - p)

        y_offset = -h
        shadow_scale = max(0.45, 1.0 - (h / self.max_height) * 0.45)
        return y_offset, shadow_scale


def ease_in_out_cubic(t: float) -> float:
    """Smooth S-curve cubic ease-in-out interpolation."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


class PieceResetReturnAnimation:
    """
    Manages smooth return animation of pieces from their post-game positions back to their starting squares.
    Surviving pieces glide home along curved trajectories, while captured pieces fly back from the panel tray.
    """
    def __init__(self, duration: float = 0.58):
        self.duration = duration
        self.elapsed: float = 0.0
        self.active: bool = False
        self.tracks: List[Dict[str, Any]] = []

    def trigger(
        self,
        end_pieces: Dict[chess.Square, chess.Piece],
        target_pieces: Dict[chess.Square, chess.Piece],
        flipped: bool,
        board_x: int,
        board_y: int,
        square_size: int,
        caps_origin: Tuple[int, int],
        piece_sizes: Dict[str, Tuple[int, int]],
    ) -> bool:
        """
        Calculates optimal flight trajectories for all pieces from their end-game squares
        back to their initial positions.
        Returns True if at least one piece moves, False otherwise.
        """
        self.tracks.clear()
        self.elapsed = 0.0

        available: Dict[Tuple[chess.Color, chess.PieceType], List[chess.Square]] = {}
        for sq, p in end_pieces.items():
            key = (p.color, p.piece_type)
            if key not in available:
                available[key] = []
            available[key].append(sq)

        sorted_targets = sorted(
            target_pieces.items(),
            key=lambda item: 0 if (item[1].color, item[1].piece_type) in available and item[0] in available[(item[1].color, item[1].piece_type)] else 1
        )

        has_any_movement = False

        for target_sq, target_piece in sorted_targets:
            key = (target_piece.color, target_piece.piece_type)
            tf = chess.square_file(target_sq)
            tr = chess.square_rank(target_sq)

            code = piece_to_code(target_piece)
            pw, ph = piece_sizes.get(code or "", (80, 80))
            tx, ty = square_to_piece_center(
                target_sq, pw, ph, flipped=flipped, board_x=board_x, board_y=board_y, square_size=square_size
            )

            matched_from_sq: Optional[chess.Square] = None
            if key in available and available[key]:
                if target_sq in available[key]:
                    matched_from_sq = target_sq
                    available[key].remove(target_sq)
                else:
                    best_idx = -1
                    best_dist = 9999
                    for idx, from_sq in enumerate(available[key]):
                        ff = chess.square_file(from_sq)
                        fr = chess.square_rank(from_sq)
                        dist = (ff - tf) ** 2 * 8 + (fr - tr) ** 2
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = idx
                    matched_from_sq = available[key].pop(best_idx)

            if matched_from_sq is not None:
                sx, sy = square_to_piece_center(
                    matched_from_sq, pw, ph, flipped=flipped, board_x=board_x, board_y=board_y, square_size=square_size
                )
                from_caps = False
            else:
                sx, sy = caps_origin
                from_caps = True

            dx = tx - sx
            dy = ty - sy
            dist = math.hypot(dx, dy)
            has_moved = (dist > 1.0)
            if has_moved:
                has_any_movement = True

            arc = min(28.0, dist * 0.08) if has_moved else 0.0

            self.tracks.append({
                "piece": target_piece,
                "code": code,
                "start_x": sx,
                "start_y": sy,
                "target_x": tx,
                "target_y": ty,
                "from_caps": from_caps,
                "has_moved": has_moved,
                "arc_height": arc,
            })

        if not has_any_movement:
            self.active = False
            return False

        self.active = True
        return True

    def update(self, dt: float) -> bool:
        """Advance return animation. Returns True when finished."""
        if not self.active:
            return False
        self.elapsed += max(0.0, dt)
        if self.elapsed >= self.duration:
            self.active = False
            return True
        return False

    def cancel(self) -> None:
        """Stop and reset the return animation."""
        self.active = False
        self.elapsed = 0.0
        self.tracks.clear()

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def progress(self) -> float:
        if not self.active or self.duration <= 0.0:
            return 1.0
        return min(1.0, self.elapsed / self.duration)


class RookDashAnimation:
    """
    Manages high-speed dashing animations for Rooks in Rook Dash mode.
    Features:
    - High-velocity linear sprint along ranks and files
    - Fiery orange / energy trail with multiple ghost afterimages
    - Luminous dash streak / speedlines connecting the start and current positions
    - Kinetic landing impact shockwave and spark bursts upon destination/capture
    """
    def __init__(self, dash_duration: float = 0.18, impact_duration: float = 0.10):
        self.dash_duration = dash_duration
        self.impact_duration = impact_duration
        self.total_duration = dash_duration + impact_duration
        self.elapsed: float = 0.0
        self.active: bool = False

        self.from_sq: Optional[chess.Square] = None
        self.to_sq: Optional[chess.Square] = None
        self.piece_code: str = ""
        self.is_capture: bool = False
        self.start_pos: Tuple[int, int] = (0, 0)
        self.target_pos: Tuple[int, int] = (0, 0)
        self.distance_squares: int = 1
        self.flipped: bool = False
        self.theme_color: Tuple[int, int, int] = (255, 130, 40)

    def trigger(
        self,
        from_sq: chess.Square,
        to_sq: chess.Square,
        piece_code: str,
        is_capture: bool,
        start_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        flipped: bool = False,
        theme_color: Tuple[int, int, int] = (255, 130, 40),
    ) -> None:
        """Initialize and begin the dash animation."""
        self.from_sq = from_sq
        self.to_sq = to_sq
        self.piece_code = piece_code
        self.is_capture = is_capture
        self.start_pos = start_pos
        self.target_pos = target_pos
        self.flipped = flipped
        self.theme_color = theme_color

        f1, r1 = chess.square_file(from_sq), chess.square_rank(from_sq)
        f2, r2 = chess.square_file(to_sq), chess.square_rank(to_sq)
        self.distance_squares = max(1, abs(f2 - f1) + abs(r2 - r1))

        # Dynamic duration: snappy sprint scaled slightly by distance
        self.dash_duration = 0.12 + 0.015 * self.distance_squares
        self.impact_duration = 0.12 if is_capture else 0.08
        self.total_duration = self.dash_duration + self.impact_duration
        self.elapsed = 0.0
        self.active = True

    def update(self, dt: float) -> bool:
        """Advance dash animation time by dt. Returns True when completed."""
        if not self.active:
            return False
        self.elapsed += max(0.0, dt)
        if self.elapsed >= self.total_duration:
            self.active = False
            return True
        return False

    def cancel(self) -> None:
        """Immediately stop dash animation."""
        self.active = False
        self.elapsed = 0.0

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def dash_progress(self) -> float:
        """Normalized dash progress from 0.0 to 1.0."""
        if not self.active or self.dash_duration <= 0:
            return 1.0
        return min(1.0, self.elapsed / self.dash_duration)

    @property
    def impact_progress(self) -> float:
        """Normalized impact/landing progress from 0.0 to 1.0."""
        if not self.active or self.elapsed < self.dash_duration:
            return 0.0
        if self.impact_duration <= 0:
            return 1.0
        return min(1.0, (self.elapsed - self.dash_duration) / self.impact_duration)



class ChessRenderer:
    """Encapsulates all Pygame drawing logic for the chess interface."""

    def __init__(
        self,
        screen: pygame.Surface,
        board_x: int = BOARD_X,
        board_y: int = BOARD_Y,
        square_size: int = SQUARE_SIZE,
        panel_x: int = 900,
        panel_width: int = 270,
    ):
        self.screen = screen
        self.board_x = board_x
        self.board_y = board_y
        self.square_size = square_size
        self.panel_x = panel_x
        self.panel_width = panel_width

        # Initialize typography with modern system font fallbacks
        def _get_font(size: int, bold: bool = False):
            return pygame.font.SysFont("segoe ui,trebuchet ms,arial", size, bold=bold)

        def _get_mono_font(size: int, bold: bool = False):
            return pygame.font.SysFont("consolas,courier new,segoe ui,arial", size, bold=bold)

        self.font_title = _get_font(25, bold=True)
        self.font_winner = _get_font(38, bold=True)
        self.font_subtitle = _get_font(13, bold=True)
        self.font_header = _get_font(17, bold=True)
        self.font_clock = _get_mono_font(21, bold=True)
        self.font_normal = _get_font(15)
        self.font_small = _get_font(13)
        self.font_micro = _get_font(11)
        self.font_coords = _get_font(12, bold=True)
        self.font_card_large = _get_font(46, bold=True)
        self.font_card_med = _get_font(22, bold=True)
        self.font_card_corner = _get_font(14, bold=True)

        self.buttons = UIButtons(panel_x, panel_width)

        # Board and piece scaling caches for adaptive fullscreen rendering
        self._cached_board_size: Optional[Tuple[int, int]] = None
        self._cached_board_scaled: Optional[pygame.Surface] = None
        self._cached_board_src: Optional[pygame.Surface] = None
        self._cached_pieces_key: Optional[Tuple[int, int]] = None
        self._cached_pieces_dict: Dict[str, pygame.Surface] = {}

        # Pre-create highlight overlays for high performance
        self._surf_selected = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        pygame.draw.rect(self._surf_selected, (255, 215, 0, 75), (0, 0, square_size, square_size))
        pygame.draw.rect(self._surf_selected, (255, 230, 80, 200), (0, 0, square_size, square_size), width=2)

        self._surf_last_move = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        pygame.draw.rect(self._surf_last_move, (50, 205, 120, 65), (0, 0, square_size, square_size))
        pygame.draw.rect(self._surf_last_move, (70, 225, 140, 130), (0, 0, square_size, square_size), width=2)

        self._surf_check = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_check.fill((235, 60, 60, 110))
        self._snail_sprite_cache: Dict[int, pygame.Surface] = {}

        # Game-start piece bounce animation manager
        self.bounce_anim = GameStartBounceAnimation()
        # Post-game piece return-to-initial-position animation manager
        self.return_anim = PieceResetReturnAnimation()
        # Rook Dash high-speed sprint & impact animation manager
        self.rook_dash_anim = RookDashAnimation()

    def update_layout(self, width: int, height: int, is_fullscreen: bool = False) -> None:
        """
        Dynamically adapt chessboard, panel, and UI geometry for the given display resolution,
        seamlessly optimizing for fullscreen mode across any monitor aspect ratio (16:9, 16:10, 21:9, etc.).
        """
        if not is_fullscreen and width == 1200 and height == 900:
            new_board_x = 50
            new_board_y = 50
            new_square_size = 100
            new_panel_width = 270
            new_panel_x = 900
        else:
            margin_y = max(24, int(height * 0.04))
            avail_h = max(300, height - 2 * margin_y)

            new_panel_width = max(270, min(330, int(width * 0.22)))
            panel_margin_right = max(24, int(width * 0.025))
            new_panel_x = width - new_panel_width - panel_margin_right

            avail_board_w = max(200, new_panel_x - 30)
            max_sq_w = (avail_board_w - 50) // 8
            max_sq_h = avail_h // 8

            new_square_size = max(40, min(max_sq_w, max_sq_h))
            board_size = 8 * new_square_size
            new_board_y = max(10, (height - board_size) // 2)
            new_board_x = max(25, (new_panel_x - board_size) // 2)

        changed = (
            new_board_x != self.board_x
            or new_board_y != self.board_y
            or new_square_size != self.square_size
            or new_panel_x != self.panel_x
            or new_panel_width != self.panel_width
        )

        self.board_x = new_board_x
        self.board_y = new_board_y
        self.square_size = new_square_size
        self.panel_x = new_panel_x
        self.panel_width = new_panel_width

        if changed:
            self.buttons = UIButtons(self.panel_x, self.panel_width)

            self._surf_selected = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            pygame.draw.rect(self._surf_selected, (255, 215, 0, 75), (0, 0, self.square_size, self.square_size))
            pygame.draw.rect(self._surf_selected, (255, 230, 80, 200), (0, 0, self.square_size, self.square_size), width=2)

            self._surf_last_move = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            pygame.draw.rect(self._surf_last_move, (50, 205, 120, 65), (0, 0, self.square_size, self.square_size))
            pygame.draw.rect(self._surf_last_move, (70, 225, 140, 130), (0, 0, self.square_size, self.square_size), width=2)

            self._surf_check = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
            self._surf_check.fill((235, 60, 60, 110))

            self._cached_board_size = None
            self._cached_board_scaled = None
            self._cached_pieces_key = None
            self._cached_pieces_dict = {}

    def get_scaled_piece_images(self, piece_images: Optional[Dict[str, pygame.Surface]]) -> Dict[str, pygame.Surface]:
        """Scale piece images to match current square_size with cached performance."""
        if not piece_images or self.square_size == 100:
            return piece_images or {}

        cache_key = (self.square_size, id(piece_images))
        if getattr(self, "_cached_pieces_key", None) == cache_key:
            return self._cached_pieces_dict

        ratio = self.square_size / 100.0
        scaled_dict = {}
        for code, img in piece_images.items():
            w = max(16, int(round(img.get_width() * ratio)))
            h = max(16, int(round(img.get_height() * ratio)))
            scaled_dict[code] = pygame.transform.smoothscale(img, (w, h))

        self._cached_pieces_key = cache_key
        self._cached_pieces_dict = scaled_dict
        return scaled_dict

    def trigger_start_bounce(self) -> None:
        """Trigger the piece bounce animation at the start of a new game."""
        self.bounce_anim.trigger()

    def update_start_bounce(self, dt: float) -> None:
        """Update piece bounce animation elapsed time."""
        self.bounce_anim.update(dt)

    def cancel_start_bounce(self) -> None:
        """Immediately stop piece bounce animation."""
        self.bounce_anim.cancel()

    def is_bounce_animating(self) -> bool:
        """Return True if pieces are currently in bounce animation."""
        return self.bounce_anim.is_active

    def trigger_reset_return(
        self,
        end_pieces: Dict[chess.Square, chess.Piece],
        game_state: GameState,
        piece_images: Dict[str, pygame.Surface],
        flipped: bool = False,
    ) -> bool:
        """
        Trigger smooth animation of pieces returning to their initial position after a game restart.
        If pieces moved, plays the glide animation; otherwise immediately triggers the start bounce.
        """
        self.cancel_start_bounce()
        target_pieces = {
            sq: game_state.get_piece_at(sq)
            for sq in chess.SQUARES
            if game_state.get_piece_at(sq) is not None
        }
        piece_sizes = {
            code: (img.get_width(), img.get_height())
            for code, img in piece_images.items()
        }
        caps_origin = (self.panel_x + 95, 625)
        started = self.return_anim.trigger(
            end_pieces=end_pieces,
            target_pieces=target_pieces,
            flipped=flipped,
            board_x=self.board_x,
            board_y=self.board_y,
            square_size=self.square_size,
            caps_origin=caps_origin,
            piece_sizes=piece_sizes,
        )
        if not started:
            # No pieces needed to move; proceed directly to bounce
            self.trigger_start_bounce()
            return False
        return True

    def update_reset_return(self, dt: float) -> bool:
        """
        Update the piece return animation.
        Automatically triggers start bounce when return animation completes.
        """
        if self.return_anim.is_active:
            finished = self.return_anim.update(dt)
            if finished:
                self.trigger_start_bounce()
                return True
        return False

    def cancel_reset_return(self) -> None:
        """Immediately stop piece return animation."""
        self.return_anim.cancel()

    def is_return_animating(self) -> bool:
        """Return True if pieces are currently animating back to their initial squares."""
        return self.return_anim.is_active

    def trigger_rook_dash(
        self,
        from_sq: chess.Square,
        to_sq: chess.Square,
        piece_code: str,
        piece_images: Dict[str, pygame.Surface],
        is_capture: bool = False,
        flipped: bool = False,
        theme_color: Tuple[int, int, int] = (255, 130, 40),
    ) -> None:
        """Start a high-speed dash animation for a piece in Dash modes."""
        scaled_images = self.get_scaled_piece_images(piece_images)
        img = scaled_images.get(piece_code)
        pw = img.get_width() if img else int(self.square_size * 0.8)
        ph = img.get_height() if img else int(self.square_size * 0.8)
        start_pos = square_to_piece_center(
            from_sq, pw, ph, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
        )
        target_pos = square_to_piece_center(
            to_sq, pw, ph, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
        )
        self.rook_dash_anim.trigger(
            from_sq=from_sq,
            to_sq=to_sq,
            piece_code=piece_code,
            is_capture=is_capture,
            start_pos=start_pos,
            target_pos=target_pos,
            flipped=flipped,
            theme_color=theme_color,
        )

    def trigger_bishop_dash(
        self,
        from_sq: chess.Square,
        to_sq: chess.Square,
        piece_code: str,
        piece_images: Dict[str, pygame.Surface],
        is_capture: bool = False,
        flipped: bool = False,
    ) -> None:
        """Start a high-speed dash animation for a Bishop in Bishop Dash mode."""
        self.trigger_rook_dash(
            from_sq=from_sq,
            to_sq=to_sq,
            piece_code=piece_code,
            piece_images=piece_images,
            is_capture=is_capture,
            flipped=flipped,
            theme_color=(185, 85, 255),
        )

    def update_rook_dash(self, dt: float) -> bool:
        """Update Rook Dash animation by dt seconds. Returns True if finished."""
        return self.rook_dash_anim.update(dt)

    def cancel_rook_dash(self) -> None:
        """Cancel and dismiss active rook dash animation."""
        self.rook_dash_anim.cancel()

    def is_dash_animating(self) -> bool:
        """Return True if a Rook is actively in mid-dash."""
        return self.rook_dash_anim.is_active

    # -------------------------------------------------------------------------
    # Board & Square Highlights
    # -------------------------------------------------------------------------

    def draw_board(self, board_image: pygame.Surface, flipped: bool = False) -> None:
        """Render the 8x8 chessboard background sprite, frame shadow, and algebraic coordinates."""
        board_w = 8 * self.square_size
        board_h = 8 * self.square_size

        # 1. Subtle ambient drop shadow around the board
        shadow_rect = pygame.Rect(self.board_x - 6, self.board_y - 6, board_w + 12, board_h + 12)
        pygame.draw.rect(self.screen, (10, 12, 16), shadow_rect, border_radius=8)

        # 2. Sleek metallic outer border frame
        frame_rect = pygame.Rect(self.board_x - 3, self.board_y - 3, board_w + 6, board_h + 6)
        pygame.draw.rect(self.screen, (46, 52, 68), frame_rect, width=3, border_radius=6)

        # 3. Blit the board background (smoothly scaled if board geometry has adapted)
        if board_image.get_size() != (board_w, board_h):
            if (
                self._cached_board_size != (board_w, board_h)
                or self._cached_board_src != board_image
                or self._cached_board_scaled is None
            ):
                self._cached_board_scaled = pygame.transform.smoothscale(board_image, (board_w, board_h))
                self._cached_board_size = (board_w, board_h)
                self._cached_board_src = board_image
            self.screen.blit(self._cached_board_scaled, (self.board_x, self.board_y))
        else:
            self.screen.blit(board_image, (self.board_x, self.board_y))

        # 4. Rank Coordinates (1 to 8) along left margin
        for row in range(8):
            rank_num = (row + 1) if flipped else (8 - row)
            lbl = self.font_coords.render(str(rank_num), True, TEXT_MUTED)
            cy = self.board_y + row * self.square_size + self.square_size // 2
            self.screen.blit(lbl, lbl.get_rect(center=(self.board_x - 16, cy)))

        # 5. File Coordinates (a to h) along bottom margin
        for col in range(8):
            file_char = chr(ord('h') - col) if flipped else chr(ord('a') + col)
            lbl = self.font_coords.render(file_char, True, TEXT_MUTED)
            cx = self.board_x + col * self.square_size + self.square_size // 2
            self.screen.blit(lbl, lbl.get_rect(center=(cx, self.board_y + board_h + 16)))

    def draw_highlights(
        self,
        game_state: GameState,
        selected_square: Optional[chess.Square],
        legal_destinations: List[chess.Square],
        flipped: bool = False,
    ) -> None:
        """
        Draw all contextual square highlights:
        - Last move from/to squares with glowing emerald aura
        - King in check alert with animated pulsing crimson halo
        - Selected piece square with luminous golden accent
        - Legal move indicators (soft anti-aliased glowing dots for empty squares, precision target rings for captures)
        """
        # 1. Last move highlight
        if game_state.last_move:
            for sq in game_state.last_move:
                rect = square_to_rect(
                    sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                self.screen.blit(self._surf_last_move, rect.topleft)

        # 2. King in check highlight (dynamic pulse)
        if game_state.is_in_check():
            king_sq = game_state.king_square()
            if king_sq is not None:
                rect = square_to_rect(
                    king_sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                pulse = int(28 * abs(math.sin(pygame.time.get_ticks() * 0.005)))
                check_surf = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                check_surf.fill((235, 50, 50, 85 + pulse))
                self.screen.blit(check_surf, rect.topleft)
                pygame.draw.rect(self.screen, (245, 60, 60), rect, width=3)

        # 3. Selected piece highlight
        if selected_square is not None:
            rect = square_to_rect(
                selected_square, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
            )
            self.screen.blit(self._surf_selected, rect.topleft)
            pygame.draw.rect(self.screen, (255, 230, 80), rect, width=2)

            # 3b. Dash Trajectory Beams (Rook Dash & Bishop Dash)
            if getattr(game_state.mode, "name", "") == "Rook Dash":
                sel_p = game_state.get_piece_at(selected_square)
                if sel_p and sel_p.piece_type == chess.ROOK:
                    sel_center = rect.center
                    for dest in legal_destinations:
                        d_rect = square_to_rect(
                            dest, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                        )
                        pygame.draw.line(self.screen, (255, 140, 50), sel_center, d_rect.center, 3)
            elif getattr(game_state.mode, "name", "") == "Bishop Dash":
                sel_p = game_state.get_piece_at(selected_square)
                if sel_p and sel_p.piece_type == chess.BISHOP:
                    sel_center = rect.center
                    for dest in legal_destinations:
                        d_rect = square_to_rect(
                            dest, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                        )
                        pygame.draw.line(self.screen, (180, 80, 255), sel_center, d_rect.center, 3)

        # 4. Legal destination indicators
        for dest in legal_destinations:
            rect = square_to_rect(
                dest, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
            )
            target_piece = game_state.get_piece_at(dest)

            # Check if this destination is an en-passant capture
            is_ep = False
            if selected_square is not None and target_piece is None:
                moving_piece = game_state.get_piece_at(selected_square)
                if moving_piece and moving_piece.piece_type == chess.PAWN:
                    if chess.square_file(selected_square) != chess.square_file(dest):
                        is_ep = True

            if target_piece is not None or is_ep:
                # Precision corner-bracket target capture ring
                ring_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                center = (self.square_size // 2, self.square_size // 2)
                rad = self.square_size // 2 - 5
                pygame.draw.circle(ring_surface, (239, 68, 68, 175), center, rad, width=4)
                for angle in [45, 135, 225, 315]:
                    r = math.radians(angle)
                    p1 = (center[0] + (rad - 6) * math.cos(r), center[1] + (rad - 6) * math.sin(r))
                    p2 = (center[0] + (rad + 1) * math.cos(r), center[1] + (rad + 1) * math.sin(r))
                    pygame.draw.line(ring_surface, (255, 115, 115, 220), p1, p2, width=2)
                self.screen.blit(ring_surface, rect.topleft)
            else:
                # Soft anti-aliased glowing move indicator dot
                dot_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                center = (self.square_size // 2, self.square_size // 2)
                pygame.draw.circle(dot_surface, (74, 222, 128, 70), center, 14)
                pygame.draw.circle(dot_surface, (74, 222, 128, 210), center, 8)
                self.screen.blit(dot_surface, rect.topleft)

    # -------------------------------------------------------------------------
    # Piece Rendering
    # -------------------------------------------------------------------------

    def draw_pieces(
        self,
        game_state: GameState,
        piece_images: Dict[str, pygame.Surface],
        dragging_square: Optional[chess.Square] = None,
        flipped: bool = False,
        apply_bounce: bool = True,
    ) -> None:
        """
        Draw all chess pieces currently on the board.
        If return-to-initial animation is active, pieces smoothly glide home along their paths.
        If bounce animation is active, pieces bounce with dynamic ground shadows.
        """
        piece_images = self.get_scaled_piece_images(piece_images)
        if self.return_anim.is_active:
            p = self.return_anim.progress
            e = ease_in_out_cubic(p)
            for track in self.return_anim.tracks:
                code = track["code"]
                if not code or code not in piece_images:
                    continue
                image = piece_images[code]
                sx, sy = track["start_x"], track["start_y"]
                tx, ty = track["target_x"], track["target_y"]
                cur_x = int(sx + (tx - sx) * e)
                cur_y = int(sy + (ty - sy) * e)

                # Parabolic vertical lift along flight path
                lift = int(4.0 * track["arc_height"] * p * (1.0 - p))
                draw_y = cur_y - lift

                # Draw drop shadow beneath moving piece
                if track["has_moved"]:
                    shadow_scale = max(0.4, 1.0 - (lift / 30.0) * 0.45)
                    shadow_w = max(4, int(self.square_size * 0.55 * shadow_scale))
                    shadow_h = max(2, int(self.square_size * 0.16 * shadow_scale))
                    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
                    shadow_alpha = int(85 * shadow_scale)
                    pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), (0, 0, shadow_w, shadow_h))
                    shadow_center = (cur_x + image.get_width() // 2, cur_y + image.get_height() - 6)
                    self.screen.blit(shadow_surf, shadow_surf.get_rect(center=shadow_center))

                # Handle fade-in for captured pieces re-entering the board
                if track["from_caps"] and p < 0.4:
                    alpha_factor = min(1.0, p / 0.4)
                    ghost = image.copy()
                    ghost.set_alpha(int(255 * alpha_factor))
                    self.screen.blit(ghost, (cur_x, draw_y))
                else:
                    self.screen.blit(image, (cur_x, draw_y))
            return

        is_bouncing = apply_bounce and self.bounce_anim.is_active
        is_dash_active = self.rook_dash_anim.is_active
        dash_to_sq = self.rook_dash_anim.to_sq if is_dash_active else None

        for sq in chess.SQUARES:
            if is_dash_active and sq == dash_to_sq:
                # Dashing piece is actively animated by draw_rook_dash_animation
                continue
            piece = game_state.get_piece_at(sq)
            if piece is None:
                continue

            code = piece_to_code(piece)
            if not code or code not in piece_images:
                continue

            image = piece_images[code]
            draw_pos = square_to_piece_center(
                sq,
                image.get_width(),
                image.get_height(),
                flipped=flipped,
                board_x=self.board_x,
                board_y=self.board_y,
                square_size=self.square_size,
            )

            # If this piece is currently being dragged, draw faint ghost in original square
            if dragging_square == sq:
                ghost = image.copy()
                ghost.set_alpha(70)
                self.screen.blit(ghost, draw_pos)
            else:
                if is_bouncing:
                    row, col = square_to_board_coords(sq, flipped=flipped)
                    is_pawn = (piece.piece_type == chess.PAWN)
                    y_offset, shadow_scale = self.bounce_anim.get_offset(col=col, is_pawn=is_pawn)

                    if y_offset < -0.5:
                        rect = square_to_rect(
                            sq,
                            flipped=flipped,
                            board_x=self.board_x,
                            board_y=self.board_y,
                            square_size=self.square_size,
                        )
                        shadow_w = max(4, int(self.square_size * 0.55 * shadow_scale))
                        shadow_h = max(2, int(self.square_size * 0.16 * shadow_scale))
                        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
                        shadow_alpha = int(90 * shadow_scale)
                        pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), (0, 0, shadow_w, shadow_h))
                        shadow_center = (rect.centerx, rect.bottom - 14)
                        self.screen.blit(shadow_surf, shadow_surf.get_rect(center=shadow_center))

                    self.screen.blit(image, (draw_pos[0], int(draw_pos[1] + y_offset)))
                else:
                    self.screen.blit(image, draw_pos)

        if is_dash_active:
            self.draw_rook_dash_animation(piece_images)

    def draw_rook_dash_animation(self, piece_images: Dict[str, pygame.Surface]) -> None:
        """
        Render the dashing rook with motion trails, energy streaks, afterimages,
        and an explosive landing impact shockwave.
        """
        if not self.rook_dash_anim.is_active:
            return

        piece_images = self.get_scaled_piece_images(piece_images)
        anim = self.rook_dash_anim
        code = anim.piece_code
        if not code or code not in piece_images:
            return

        image = piece_images[code]
        pw, ph = image.get_width(), image.get_height()
        sx, sy = anim.start_pos
        tx, ty = anim.target_pos

        p = anim.dash_progress
        # Snappy cubic ease-out for energetic burst deceleration
        e = 1.0 - (1.0 - p) ** 3
        cur_x = sx + (tx - sx) * e
        cur_y = sy + (ty - sy) * e

        c_sx = sx + pw // 2
        c_sy = sy + ph // 2
        c_cx = cur_x + pw // 2
        c_cy = cur_y + ph // 2
        c_tx = tx + pw // 2
        c_ty = ty + ph // 2

        tc = getattr(anim, "theme_color", (255, 130, 40))
        glow_col = tc
        mid_col = (min(255, tc[0] + 35), min(255, tc[1] + 35), min(255, tc[2] + 35))
        core_col = (255, 245, 220) if tc[0] > 200 and tc[2] < 100 else (250, 235, 255)
        spark_col = (255, 215, 70) if tc[0] > 200 and tc[2] < 100 else (225, 175, 255)

        # 1. Dash Energy Streaks & Beam
        dx = c_cx - c_sx
        dy = c_cy - c_sy
        dist = math.hypot(dx, dy)
        if dist > 4.0:
            beam_surf = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
            beam_alpha = max(0, min(255, int(130 * (1.0 - anim.impact_progress * 0.8))))
            # Wide warm outer glow
            pygame.draw.line(beam_surf, (glow_col[0], glow_col[1], glow_col[2], beam_alpha), (c_sx, c_sy), (c_cx, c_cy), 22)
            # Vibrant mid-beam
            pygame.draw.line(beam_surf, (mid_col[0], mid_col[1], mid_col[2], min(255, int(beam_alpha * 1.5))), (c_sx, c_sy), (c_cx, c_cy), 8)
            # Bright core streak
            pygame.draw.line(beam_surf, (core_col[0], core_col[1], core_col[2], min(255, int(beam_alpha * 2.0))), (c_sx, c_sy), (c_cx, c_cy), 3)

            # Parallel speed lines (wind resistance streaks)
            nx, ny = -dy / dist, dx / dist
            for offset in (-16, 16):
                ox1, oy1 = c_sx + nx * offset, c_sy + ny * offset
                ox2, oy2 = c_cx + nx * offset, c_cy + ny * offset
                sl_alpha = max(0, min(255, int(80 * (1.0 - anim.impact_progress))))
                pygame.draw.line(beam_surf, (mid_col[0], mid_col[1], mid_col[2], sl_alpha), (ox1, oy1), (ox2, oy2), 2)

            self.screen.blit(beam_surf, (0, 0))

        # 2. Ghost Afterimages (Motion Blur Trail)
        if p < 1.0 or anim.impact_progress < 0.6:
            ghost_lags = [0.08, 0.16, 0.24, 0.32]
            ghost_alphas = [140, 95, 55, 25]
            fade = max(0.0, 1.0 - anim.impact_progress)
            for lag, base_alpha in zip(ghost_lags, ghost_alphas):
                prev_p = p - lag
                if prev_p > 0.01:
                    ge = 1.0 - (1.0 - prev_p) ** 3
                    gx = int(sx + (tx - sx) * ge)
                    gy = int(sy + (ty - sy) * ge)
                    ghost = image.copy()
                    ghost.set_alpha(max(0, min(255, int(base_alpha * fade))))
                    tint = pygame.Surface(image.get_size(), pygame.SRCALPHA)
                    tint.fill((glow_col[0], glow_col[1], glow_col[2], max(0, min(255, int(60 * fade)))))
                    ghost.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                    self.screen.blit(ghost, (gx, gy))

        # 3. Dynamic Ground Shadow
        shadow_w = max(4, int(self.square_size * 0.65))
        shadow_h = max(2, int(self.square_size * 0.18))
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 110), (0, 0, shadow_w, shadow_h))
        shadow_center = (int(cur_x + pw // 2), int(cur_y + ph - 2))
        self.screen.blit(shadow_surf, shadow_surf.get_rect(center=shadow_center))

        # 4. Main Dashing Piece Sprite
        self.screen.blit(image, (int(cur_x), int(cur_y)))

        # 5. Landing Impact Shockwave & Burst Particles
        ip = anim.impact_progress
        if p >= 0.90 or ip > 0.0:
            eff_ip = ip if ip > 0.0 else (p - 0.90) / 0.10 * 0.15
            shock_surf = pygame.Surface((self.screen.get_width(), self.screen.get_height()), pygame.SRCALPHA)
            fade = max(0.0, 1.0 - eff_ip)

            max_r = 52 if anim.is_capture else 38
            r1 = int(10 + eff_ip * max_r)
            w1 = max(1, int(4 * fade))
            pygame.draw.circle(shock_surf, (glow_col[0], glow_col[1], glow_col[2], int(220 * fade)), (int(c_tx), int(c_ty)), r1, width=w1)

            r2 = int(6 + eff_ip * (max_r * 0.6))
            w2 = max(1, int(2 * fade))
            pygame.draw.circle(shock_surf, (core_col[0], core_col[1], core_col[2], int(255 * fade)), (int(c_tx), int(c_ty)), r2, width=w2)

            if anim.is_capture:
                spark_dist = 14 + eff_ip * 45
                spark_size = max(2, int(5 * fade))
                for angle_deg in (0, 45, 90, 135, 180, 225, 270, 315):
                    rad = math.radians(angle_deg)
                    spx = int(c_tx + spark_dist * math.cos(rad))
                    spy = int(c_ty + spark_dist * math.sin(rad))
                    pygame.draw.circle(shock_surf, (spark_col[0], spark_col[1], spark_col[2], int(240 * fade)), (spx, spy), spark_size)

            self.screen.blit(shock_surf, (0, 0))

    def draw_dragged_piece(
        self,
        piece_images: Dict[str, pygame.Surface],
        piece_code: str,
        mouse_pos: Tuple[int, int],
    ) -> None:
        """Render the floating piece sprite directly centered on the mouse cursor."""
        piece_images = self.get_scaled_piece_images(piece_images)
        if piece_code not in piece_images:
            return
        image = piece_images[piece_code]
        rect = image.get_rect(center=mouse_pos)
        self.screen.blit(image, rect)

    # -------------------------------------------------------------------------
    # Immortal Snail Graphics & Entity Overlay
    # -------------------------------------------------------------------------

    def get_snail_sprite(self, size: int = 76, team_color: chess.Color = chess.WHITE) -> pygame.Surface:
        """Create and cache high-res distinctive Immortal Snail sprites for White and Black teams."""
        cache_key = (size, team_color)
        if cache_key in self._snail_sprite_cache:
            return self._snail_sprite_cache[cache_key]

        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        is_white_team = (team_color == chess.WHITE)

        # 1. Slime footprint glow
        slime_w = int(size * 0.88)
        slime_h = int(size * 0.22)
        slime_glow_color = (110, 245, 215, 95) if is_white_team else (245, 80, 80, 95)
        pygame.draw.ellipse(surf, slime_glow_color, (int(size * 0.06), size - slime_h - 2, slime_w, slime_h))

        # 2. Body foot / slug base
        foot_w = int(size * 0.78)
        foot_h = int(size * 0.24)
        foot_rect = pygame.Rect(int(size * 0.12), size - foot_h - 4, foot_w, foot_h)
        foot_color = (220, 230, 215) if is_white_team else (70, 65, 78)
        foot_outline = (130, 150, 125) if is_white_team else (35, 30, 42)
        pygame.draw.ellipse(surf, foot_color, foot_rect)
        pygame.draw.ellipse(surf, foot_outline, foot_rect, 2)

        # 3. Head & Eyestalks
        head_cx = int(size * 0.76)
        head_cy = int(size * 0.65)
        head_r = int(size * 0.15)
        head_color = (225, 235, 220) if is_white_team else (78, 72, 85)
        pygame.draw.circle(surf, head_color, (head_cx, head_cy), head_r)
        pygame.draw.circle(surf, foot_outline, (head_cx, head_cy), head_r, 2)

        stalk1_tip = (head_cx - 4, head_cy - int(size * 0.26))
        stalk2_tip = (head_cx + 7, head_cy - int(size * 0.23))
        pygame.draw.line(surf, foot_outline, (head_cx - 4, head_cy - 4), stalk1_tip, 3)
        pygame.draw.line(surf, foot_outline, (head_cx + 4, head_cy - 4), stalk2_tip, 3)

        # Shiny eyes with white highlights
        for tip in (stalk1_tip, stalk2_tip):
            pygame.draw.circle(surf, (255, 255, 255), tip, 4)
            pupil_color = (25, 25, 35) if is_white_team else (235, 50, 50)
            pygame.draw.circle(surf, pupil_color, (tip[0] + 1, tip[1]), 2)

        # 4. Stylized Shell
        shell_center = (int(size * 0.44), int(size * 0.44))
        shell_r = int(size * 0.38)
        shell_color = (245, 230, 185) if is_white_team else (48, 38, 48)
        shell_border = (145, 120, 60) if is_white_team else (25, 18, 25)
        pygame.draw.circle(surf, shell_color, shell_center, shell_r)
        pygame.draw.circle(surf, shell_border, shell_center, shell_r, 2)

        # Concentric spiral whorls
        if is_white_team:
            whorl_colors = [(0.78, (255, 205, 75)), (0.55, (220, 180, 50)), (0.32, (255, 230, 140))]
        else:
            whorl_colors = [(0.78, (235, 95, 45)), (0.55, (180, 50, 30)), (0.32, (255, 140, 60))]

        for factor, col in whorl_colors:
            r = int(shell_r * factor)
            if r > 4:
                pygame.draw.circle(surf, col, shell_center, r, 2)
        center_pip = (255, 240, 180) if is_white_team else (255, 120, 70)
        pygame.draw.circle(surf, center_pip, shell_center, max(3, int(shell_r * 0.16)))

        # Specular gloss highlight
        hl_w = int(shell_r * 0.95)
        hl_h = int(shell_r * 0.48)
        pygame.draw.ellipse(surf, (255, 255, 255, 120), (shell_center[0] - shell_r + 4, shell_center[1] - shell_r + 4, hl_w, hl_h))

        self._snail_sprite_cache[cache_key] = surf
        return surf

    def draw_snail(self, game_state: GameState, flipped: bool = False) -> None:
        """Render both Immortal Snails, their slime trails, and pursuit reticles."""
        if not hasattr(game_state.mode, "snails"):
            return
        mode = game_state.mode
        snails = mode.snails

        for snail in snails:
            is_white_team = (snail.team_color == chess.WHITE)

            # 1. Slime Trail
            if snail.trail:
                trail_color = (110, 240, 210, 45) if is_white_team else (240, 80, 80, 45)
                trail_inner = (160, 255, 235, 70) if is_white_team else (255, 130, 110, 70)
                for (f, r) in snail.trail:
                    if 0 <= f <= 7 and 0 <= r <= 7:
                        t_sq = chess.square(f, r)
                        t_rect = square_to_rect(
                            t_sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                        )
                        slime_surf = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                        pygame.draw.circle(slime_surf, trail_color, (self.square_size // 2, self.square_size // 2), 15)
                        pygame.draw.circle(slime_surf, trail_inner, (self.square_size // 2, self.square_size // 2), 7)
                        self.screen.blit(slime_surf, t_rect)

            # 2. Target King Pursued Reticle
            target_sq = game_state.king_square(snail.target_color)
            if target_sq is not None:
                k_rect = square_to_rect(
                    target_sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                pulse = abs(math.sin(pygame.time.get_ticks() / 280))
                k_glow = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                glow_alpha = int(70 + 80 * pulse)
                reticle_color = (90, 230, 210, glow_alpha) if is_white_team else (245, 80, 80, glow_alpha)
                line_color = (140, 255, 230, glow_alpha) if is_white_team else (255, 110, 110, glow_alpha)

                pygame.draw.rect(k_glow, reticle_color, (0, 0, self.square_size, self.square_size), width=3, border_radius=4)
                b_len = 12
                pygame.draw.line(k_glow, line_color, (0, 0), (b_len, 0), 2)
                pygame.draw.line(k_glow, line_color, (0, 0), (0, b_len), 2)
                pygame.draw.line(k_glow, line_color, (self.square_size - 1, 0), (self.square_size - 1 - b_len, 0), 2)
                pygame.draw.line(k_glow, line_color, (self.square_size - 1, 0), (self.square_size - 1, b_len), 2)
                pygame.draw.line(k_glow, line_color, (0, self.square_size - 1), (b_len, self.square_size - 1), 2)
                pygame.draw.line(k_glow, line_color, (0, self.square_size - 1), (0, self.square_size - 1 - b_len), 2)
                pygame.draw.line(k_glow, line_color, (self.square_size - 1, self.square_size - 1), (self.square_size - 1 - b_len, self.square_size - 1), 2)
                pygame.draw.line(k_glow, line_color, (self.square_size - 1, self.square_size - 1), (self.square_size - 1, self.square_size - 1 - b_len), 2)
                self.screen.blit(k_glow, k_rect)

            # 3. Draw Snail Entity
            snail_sprite = self.get_snail_sprite(size=int(self.square_size * 0.76), team_color=snail.team_color)
            if snail.is_on_board and snail.square is not None:
                s_rect = square_to_rect(
                    snail.square, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                spr_rect = snail_sprite.get_rect(center=s_rect.center)
                if self.bounce_anim.is_active:
                    _, col = square_to_board_coords(snail.square, flipped=flipped)
                    y_off, _ = self.bounce_anim.get_offset(col=col, is_pawn=False)
                    spr_rect.y += int(y_off)
                self.screen.blit(snail_sprite, spr_rect)
            else:
                # Off-board spawn point
                f, r = snail.current_pos
                col = f if not flipped else 7 - f
                row = (7 - r) if not flipped else r
                cx = self.board_x + col * self.square_size + self.square_size // 2
                cy = self.board_y + row * self.square_size + self.square_size // 2

                badge_rect = pygame.Rect(0, 0, 96, 22)
                badge_rect.center = (cx, cy - 28)
                badge_bg = (34, 48, 44) if is_white_team else (48, 34, 38)
                badge_border = (110, 240, 210) if is_white_team else (245, 90, 90)
                badge_text_col = (130, 255, 225) if is_white_team else (255, 110, 110)
                badge_name = "WHITE SNAIL" if is_white_team else "BLACK SNAIL"

                pygame.draw.rect(self.screen, badge_bg, badge_rect, border_radius=6)
                pygame.draw.rect(self.screen, badge_border, badge_rect, width=1, border_radius=6)
                entry_lbl = self.font_micro.render(badge_name, True, badge_text_col)
                self.screen.blit(entry_lbl, entry_lbl.get_rect(center=badge_rect.center))

                spr_rect = snail_sprite.get_rect(center=(cx, cy))
                self.screen.blit(snail_sprite, spr_rect)

    # -------------------------------------------------------------------------
    # Promotion Modal
    # -------------------------------------------------------------------------

    def get_promotion_options(
        self,
        color: chess.Color,
        to_square: chess.Square,
        flipped: bool = False,
    ) -> List[Tuple[int, pygame.Rect, str]]:
        """
        Compute clickable rectangles for the 4 promotion choices:
        Queen, Rook, Bishop, Knight.
        """
        rect = square_to_rect(
            to_square, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
        )
        color_prefix = "w" if color == chess.WHITE else "b"

        modal_w = 220
        modal_h = 100
        modal_x = min(max(rect.centerx - modal_w // 2, self.board_x + 10), self.board_x + 8 * self.square_size - modal_w - 10)
        modal_y = min(max(rect.centery - modal_h // 2, self.board_y + 10), self.board_y + 8 * self.square_size - modal_h - 10)

        pieces_spec = [
            (chess.QUEEN, f"{color_prefix}q"),
            (chess.ROOK, f"{color_prefix}r"),
            (chess.BISHOP, f"{color_prefix}b"),
            (chess.KNIGHT, f"{color_prefix}k"),
        ]

        options = []
        btn_w = 48
        btn_h = 64
        spacing = 6
        start_x = modal_x + (modal_w - (4 * btn_w + 3 * spacing)) // 2
        btn_y = modal_y + 26

        for i, (ptype, pcode) in enumerate(pieces_spec):
            btn_rect = pygame.Rect(start_x + i * (btn_w + spacing), btn_y, btn_w, btn_h)
            options.append((ptype, btn_rect, pcode))

        return options

    def draw_promotion_modal(
        self,
        color: chess.Color,
        to_square: chess.Square,
        piece_images: Dict[str, pygame.Surface],
        mouse_pos: Tuple[int, int],
        flipped: bool = False,
    ) -> None:
        """Render the modal dialog allowing the player to select promotion piece."""
        piece_images = self.get_scaled_piece_images(piece_images)
        rect = square_to_rect(
            to_square, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
        )

        modal_w = 230
        modal_h = 105
        modal_x = min(max(rect.centerx - modal_w // 2, self.board_x + 10), self.board_x + 8 * self.square_size - modal_w - 10)
        modal_y = min(max(rect.centery - modal_h // 2, self.board_y + 10), self.board_y + 8 * self.square_size - modal_h - 10)
        modal_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)

        # Backdrop shadow
        shadow_rect = modal_rect.inflate(8, 8)
        pygame.draw.rect(self.screen, (10, 12, 16), shadow_rect, border_radius=12)

        # Modal body
        pygame.draw.rect(self.screen, PANEL_CARD_BG, modal_rect, border_radius=10)
        pygame.draw.rect(self.screen, ACCENT_COLOR, modal_rect, width=2, border_radius=10)

        # Title
        title_text = self.font_subtitle.render("CHOOSE PROMOTION", True, TEXT_PRIMARY)
        title_rect = title_text.get_rect(centerx=modal_rect.centerx, top=modal_y + 8)
        self.screen.blit(title_text, title_rect)

        # Draw options
        options = self.get_promotion_options(color, to_square, flipped=flipped)
        for _, btn_rect, pcode in options:
            is_hovered = btn_rect.collidepoint(mouse_pos)
            btn_bg = BTN_HOVER if is_hovered else BTN_COLOR
            pygame.draw.rect(self.screen, btn_bg, btn_rect, border_radius=6)
            pygame.draw.rect(self.screen, ACCENT_COLOR if is_hovered else BTN_BORDER, btn_rect, width=1, border_radius=6)

            if pcode in piece_images:
                img = piece_images[pcode]
                scaled = pygame.transform.smoothscale(img, (38, 38))
                img_rect = scaled.get_rect(center=(btn_rect.centerx, btn_rect.centery))
                self.screen.blit(scaled, img_rect)

    # -------------------------------------------------------------------------
    # Game Over / Winning Title Popup (Middle of Board with 50% Transparency)
    # -------------------------------------------------------------------------

    def get_game_over_popup_rect(self) -> pygame.Rect:
        """Return the centered bounding rect of the game over popup in the middle of the board."""
        cx = self.board_x + 4 * self.square_size
        cy = self.board_y + 4 * self.square_size
        popup_w, popup_h = 480, 200
        return pygame.Rect(cx - popup_w // 2, cy - popup_h // 2, popup_w, popup_h)

    def get_game_over_restart_rect(self) -> pygame.Rect:
        """Return the screen rect for the 'PLAY AGAIN' button inside the popup."""
        popup_rect = self.get_game_over_popup_rect()
        btn_w, btn_h = 190, 36
        btn_x = popup_rect.centerx - btn_w // 2
        btn_y = popup_rect.bottom - 48
        return pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    def draw_game_over_popup(
        self,
        game_state: GameState,
        mouse_pos: Tuple[int, int] = (0, 0),
    ) -> pygame.Rect:
        """
        Draw a winning title popup in the middle of the board with 50% transparency.
        Displays 'WHITE WINS' or 'BLACK WINS' (or 'TIE / DRAW'), reason, and interactive restart button.
        """
        popup_rect = self.get_game_over_popup_rect()
        popup_w, popup_h = popup_rect.width, popup_rect.height

        winner = game_state.winner()
        reason = game_state.game_over_reason() or "Game Over"

        # Theme styling based on winner
        if winner == chess.WHITE:
            title_text = "WHITE WINS"
            badge_text = "★ VICTORY ★"
            accent_rgb = (255, 215, 80)      # Champion gold
            title_color = (255, 248, 220)    # Warm bright ivory
            badge_color = (255, 215, 90)
            btn_bg_base = (45, 65, 50)
        elif winner == chess.BLACK:
            title_text = "BLACK WINS"
            badge_text = "★ VICTORY ★"
            accent_rgb = (240, 90, 90)       # Ruby crimson / obsidian
            title_color = (255, 225, 225)    # Cool crimson white
            badge_color = (255, 120, 120)
            btn_bg_base = (65, 40, 45)
        else:
            title_text = "TIE / DRAW"
            badge_text = "★ MATCH TIED ★"
            accent_rgb = (130, 185, 240)     # Cool silver cyan
            title_color = (235, 245, 255)
            badge_color = (140, 200, 255)
            btn_bg_base = (40, 50, 65)

        # 50% transparent surface (alpha = 128)
        popup_surf = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)

        # 1. Background card filled with 50% opacity dark glass (alpha 128)
        # Allows underlying board squares and pieces to show through
        pygame.draw.rect(popup_surf, (14, 18, 25, 128), (0, 0, popup_w, popup_h), border_radius=18)

        # 2. Border with 50% transparency (alpha 128)
        border_rgba = (accent_rgb[0], accent_rgb[1], accent_rgb[2], 128)
        pygame.draw.rect(popup_surf, border_rgba, (0, 0, popup_w, popup_h), width=3, border_radius=18)

        # Inner subtle highlight outline
        inner_rgba = (255, 255, 255, 30)
        pygame.draw.rect(popup_surf, inner_rgba, (3, 3, popup_w - 6, popup_h - 6), width=1, border_radius=15)

        # 3. Top badge
        b_surf = self.font_micro.render(badge_text, True, badge_color)
        popup_surf.blit(b_surf, b_surf.get_rect(center=(popup_w // 2, 24)))

        # 4. Main Winning Title: 'WHITE WINS' or 'BLACK WINS'
        t_surf = self.font_winner.render(title_text, True, title_color)
        popup_surf.blit(t_surf, t_surf.get_rect(center=(popup_w // 2, 58)))

        # 5. Outcome Reason subtitle
        r_text = reason if len(reason) <= 46 else reason[:43] + "..."
        r_surf = self.font_small.render(r_text, True, (215, 220, 230))
        popup_surf.blit(r_surf, r_surf.get_rect(center=(popup_w // 2, 98)))

        # 6. Interactive 'PLAY AGAIN' button
        btn_rect_local = pygame.Rect((popup_w - 190) // 2, popup_h - 52, 190, 36)
        restart_rect_screen = self.get_game_over_restart_rect()
        is_btn_hovered = restart_rect_screen.collidepoint(mouse_pos)

        btn_bg = (accent_rgb[0] // 3 + 40, accent_rgb[1] // 3 + 40, accent_rgb[2] // 3 + 40, 180) if is_btn_hovered else (btn_bg_base[0], btn_bg_base[1], btn_bg_base[2], 140)
        pygame.draw.rect(popup_surf, btn_bg, btn_rect_local, border_radius=8)
        pygame.draw.rect(popup_surf, (accent_rgb[0], accent_rgb[1], accent_rgb[2], 220 if is_btn_hovered else 150), btn_rect_local, width=2 if is_btn_hovered else 1, border_radius=8)

        btn_lbl = self.font_subtitle.render("PLAY AGAIN [R]", True, (255, 255, 255) if is_btn_hovered else (230, 235, 245))
        popup_surf.blit(btn_lbl, btn_lbl.get_rect(center=btn_rect_local.center))

        # 7. Blit popup to screen at centered board position
        self.screen.blit(popup_surf, popup_rect.topleft)

        return restart_rect_screen

    # -------------------------------------------------------------------------
    # Game Mode Selection Start Menu / Modal
    # -------------------------------------------------------------------------

    def get_mode_selector_rects(self) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """Return clickable rectangles for (Classic, UNO, Snail, Queen_Pawn, Rook_Dash, Bishop_Dash)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        card_w, card_h = 158, 185
        gap = 8
        total_w = card_w * 6 + gap * 5
        start_x = (screen_w - total_w) // 2
        offset_y = 0 if screen_h <= 900 else max(0, (screen_h - 700) // 2)
        card_y = 96 + offset_y

        rect_classic = pygame.Rect(start_x, card_y, card_w, card_h)
        rect_uno = pygame.Rect(start_x + (card_w + gap) * 1, card_y, card_w, card_h)
        rect_snail = pygame.Rect(start_x + (card_w + gap) * 2, card_y, card_w, card_h)
        rect_queen_pawn = pygame.Rect(start_x + (card_w + gap) * 3, card_y, card_w, card_h)
        rect_rook_dash = pygame.Rect(start_x + (card_w + gap) * 4, card_y, card_w, card_h)
        rect_bishop_dash = pygame.Rect(start_x + (card_w + gap) * 5, card_y, card_w, card_h)
        return rect_classic, rect_uno, rect_snail, rect_queen_pawn, rect_rook_dash, rect_bishop_dash

    def get_mode_selector_ai_rects(
        self,
    ) -> Tuple[
        pygame.Rect,
        pygame.Rect,
        List[Tuple[pygame.Rect, BotDifficulty]],
        Tuple[pygame.Rect, pygame.Rect, pygame.Rect],
        pygame.Rect,
    ]:
        """Return clickable rectangles for AI bot settings in the modal."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        card_w = 216
        gap = 14
        total_w = card_w * 4 + gap * 3
        start_x = (screen_w - total_w) // 2
        offset_y = 0 if screen_h <= 900 else max(0, (screen_h - 700) // 2)

        # Row 1: Game Type & Side Selection (y = 348 + offset_y)
        rect_vs_bot = pygame.Rect(start_x, 348 + offset_y, 195, 30)
        rect_vs_local = pygame.Rect(start_x + 205, 348 + offset_y, 195, 30)

        # Side selection buttons (White, Random, Black)
        side_start_x = start_x + 520
        btn_side_w = 118
        side_gap = 8
        rect_side_white = pygame.Rect(side_start_x, 348 + offset_y, btn_side_w, 30)
        rect_side_random = pygame.Rect(side_start_x + btn_side_w + side_gap, 348 + offset_y, btn_side_w, 30)
        rect_side_black = pygame.Rect(side_start_x + (btn_side_w + side_gap) * 2, 348 + offset_y, btn_side_w, 30)
        side_rects = (rect_side_white, rect_side_random, rect_side_black)

        # Row 2: 4 Difficulty Cards (y = 390 + offset_y, height = 56)
        diff_rects = [
            (pygame.Rect(start_x + i * (card_w + gap), 390 + offset_y, card_w, 56), diff)
            for i, diff in enumerate(BotDifficulty)
        ]

        # Start match prominent button (y = 604 + offset_y)
        rect_start_match = pygame.Rect(screen_w // 2 - 160, 604 + offset_y, 320, 40)

        return rect_vs_bot, rect_vs_local, diff_rects, side_rects, rect_start_match

    def get_mode_selector_timer_rects(self) -> Tuple[List[Tuple[pygame.Rect, Optional[int]]], pygame.Rect, pygame.Rect]:
        """Return preset rects [(rect, seconds), ...] and (minus_rect, plus_rect) for the start modal."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        presets = [
            ("Unlimited", None),
            ("1 min", 60),
            ("3 min", 180),
            ("5 min", 300),
            ("10 min", 600),
            ("15 min", 900),
            ("30 min", 1800),
        ]
        btn_w, btn_h = 94, 28
        gap = 10
        total_w = len(presets) * btn_w + (len(presets) - 1) * gap
        start_x = (screen_w - total_w) // 2
        offset_y = 0 if screen_h <= 900 else max(0, (screen_h - 700) // 2)
        y = 512 + offset_y

        preset_rects = []
        for i, (_, sec) in enumerate(presets):
            r = pygame.Rect(start_x + i * (btn_w + gap), y, btn_w, btn_h)
            preset_rects.append((r, sec))

        minus_rect = pygame.Rect(screen_w // 2 - 96, 552 + offset_y, 38, 26)
        plus_rect = pygame.Rect(screen_w // 2 + 58, 552 + offset_y, 38, 26)
        return preset_rects, minus_rect, plus_rect

    def draw_mode_selector_modal(
        self,
        mouse_pos: Tuple[int, int],
        timer: Optional[ChessTimer] = None,
        bot_controller: Optional[ChessBotController] = None,
    ) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """
        Draw a modal start menu allowing the player to select the game mode, opponent/AI difficulty, and match timer.
        Returns the six mode card Rects for event collision checking.
        """
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        offset_y = 0 if screen_h <= 900 else max(0, (screen_h - 700) // 2)

        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((12, 14, 18, 238))
        self.screen.blit(overlay, (0, 0))

        title_y = 38 + offset_y
        title_surf = self.font_title.render("SELECT GAME MODE & OPPONENT", True, TEXT_PRIMARY)
        t_rect = title_surf.get_rect(center=(screen_w // 2, title_y))
        self.screen.blit(title_surf, t_rect)

        sub_surf = self.font_normal.render("Select game mode [1-6], match timer, and AI difficulty before starting", True, TEXT_SECONDARY)
        s_rect = sub_surf.get_rect(center=(screen_w // 2, title_y + 26))
        self.screen.blit(sub_surf, s_rect)

        rect_classic, rect_uno, rect_snail, rect_queen_pawn, rect_rook_dash, rect_bishop_dash = self.get_mode_selector_rects()

        # 1. Classic Chess Card
        is_hov_c = rect_classic.collidepoint(mouse_pos)
        c_bg = (52, 57, 70) if is_hov_c else (40, 44, 54)
        c_border = ACCENT_COLOR if is_hov_c else PANEL_BORDER
        pygame.draw.rect(self.screen, c_bg, rect_classic, border_radius=10)
        pygame.draw.rect(self.screen, c_border, rect_classic, width=2 if is_hov_c else 1, border_radius=10)

        c_title = self.font_header.render("1. Classic", True, TEXT_PRIMARY)
        self.screen.blit(c_title, (rect_classic.x + 10, rect_classic.y + 12))
        c_badge = self.font_micro.render("STANDARD FIDE RULES", True, ACCENT_COLOR)
        self.screen.blit(c_badge, (rect_classic.x + 10, rect_classic.y + 32))

        c_lines = [
            "• Traditional rules",
            "• Castling & En Passant",
            "• Promotion choice",
            "• Checkmate to win",
        ]
        for idx, line in enumerate(c_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_classic.x + 10, rect_classic.y + 52 + idx * 19))

        btn_c_rect = pygame.Rect(rect_classic.x + 10, rect_classic.bottom - 36, rect_classic.width - 20, 26)
        btn_c_color = ACCENT_HOVER if is_hov_c else ACCENT_COLOR
        pygame.draw.rect(self.screen, btn_c_color, btn_c_rect, border_radius=5)
        btn_c_lbl = self.font_subtitle.render("PLAY [1]", True, (15, 35, 25))
        self.screen.blit(btn_c_lbl, btn_c_lbl.get_rect(center=btn_c_rect.center))

        # 2. Chess + UNO Card
        is_hov_u = rect_uno.collidepoint(mouse_pos)
        u_bg = (52, 57, 70) if is_hov_u else (40, 44, 54)
        u_border = GOLD_COLOR if is_hov_u else PANEL_BORDER
        pygame.draw.rect(self.screen, u_bg, rect_uno, border_radius=10)
        pygame.draw.rect(self.screen, u_border, rect_uno, width=2 if is_hov_u else 1, border_radius=10)

        u_title = self.font_header.render("2. UNO Chess", True, GOLD_COLOR)
        self.screen.blit(u_title, (rect_uno.x + 10, rect_uno.y + 12))
        u_badge = self.font_micro.render("CARD POWER-UPS", True, (240, 160, 60))
        self.screen.blit(u_badge, (rect_uno.x + 10, rect_uno.y + 32))

        u_lines = [
            "• Card draw each turn",
            "• 1, 2, or 3 moves",
            "• Reverse flips table",
            "• Skip turns & auto-deck",
        ]
        for idx, line in enumerate(u_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_uno.x + 10, rect_uno.y + 52 + idx * 19))

        btn_u_rect = pygame.Rect(rect_uno.x + 10, rect_uno.bottom - 36, rect_uno.width - 20, 26)
        btn_u_color = (255, 215, 90) if is_hov_u else GOLD_COLOR
        pygame.draw.rect(self.screen, btn_u_color, btn_u_rect, border_radius=5)
        btn_u_lbl = self.font_subtitle.render("PLAY [2]", True, (35, 30, 10))
        self.screen.blit(btn_u_lbl, btn_u_lbl.get_rect(center=btn_u_rect.center))

        # 3. Immortal Snail Card
        is_hov_s = rect_snail.collidepoint(mouse_pos)
        s_bg = (52, 57, 70) if is_hov_s else (40, 44, 54)
        s_border = (140, 230, 90) if is_hov_s else PANEL_BORDER
        pygame.draw.rect(self.screen, s_bg, rect_snail, border_radius=10)
        pygame.draw.rect(self.screen, s_border, rect_snail, width=2 if is_hov_s else 1, border_radius=10)

        s_title = self.font_header.render("3. Snail Chess", True, (140, 230, 90))
        self.screen.blit(s_title, (rect_snail.x + 10, rect_snail.y + 12))
        s_badge = self.font_micro.render("RELENTLESS PURSUIT", True, (160, 240, 100))
        self.screen.blit(s_badge, (rect_snail.x + 10, rect_snail.y + 32))

        s_lines = [
            "• Steps 1 tile / 5 moves",
            "• Relentlessly hunts king",
            "• Crushes routing pieces",
            "• Caught = Instant defeat",
        ]
        for idx, line in enumerate(s_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_snail.x + 10, rect_snail.y + 52 + idx * 19))

        btn_s_rect = pygame.Rect(rect_snail.x + 10, rect_snail.bottom - 36, rect_snail.width - 20, 26)
        btn_s_color = (165, 245, 110) if is_hov_s else (135, 220, 85)
        pygame.draw.rect(self.screen, btn_s_color, btn_s_rect, border_radius=5)
        btn_s_lbl = self.font_subtitle.render("PLAY [3]", True, (15, 35, 15))
        self.screen.blit(btn_s_lbl, btn_s_lbl.get_rect(center=btn_s_rect.center))

        # 4. Queen Pawn Game Card
        is_hov_qp = rect_queen_pawn.collidepoint(mouse_pos)
        qp_bg = (52, 57, 70) if is_hov_qp else (40, 44, 54)
        qp_border = (245, 105, 180) if is_hov_qp else PANEL_BORDER
        pygame.draw.rect(self.screen, qp_bg, rect_queen_pawn, border_radius=10)
        pygame.draw.rect(self.screen, qp_border, rect_queen_pawn, width=2 if is_hov_qp else 1, border_radius=10)

        qp_title = self.font_header.render("4. Queen Pawn", True, (245, 105, 180))
        self.screen.blit(qp_title, (rect_queen_pawn.x + 10, rect_queen_pawn.y + 12))
        qp_badge = self.font_micro.render("QUEEN & PAWNS CLASH", True, (255, 150, 205))
        self.screen.blit(qp_badge, (rect_queen_pawn.x + 10, rect_queen_pawn.y + 32))

        qp_lines = [
            "• Pawns on ranks 4 & 5",
            "• Queens start d1 & d8",
            "• Capture pawns to win",
            "• Tie if only Queens left",
        ]
        for idx, line in enumerate(qp_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_queen_pawn.x + 10, rect_queen_pawn.y + 52 + idx * 19))

        btn_qp_rect = pygame.Rect(rect_queen_pawn.x + 10, rect_queen_pawn.bottom - 36, rect_queen_pawn.width - 20, 26)
        btn_qp_color = (255, 135, 195) if is_hov_qp else (225, 95, 170)
        pygame.draw.rect(self.screen, btn_qp_color, btn_qp_rect, border_radius=5)
        btn_qp_lbl = self.font_subtitle.render("PLAY [4]", True, (35, 15, 25))
        self.screen.blit(btn_qp_lbl, btn_qp_lbl.get_rect(center=btn_qp_rect.center))

        # 5. Rook Dash Card
        is_hov_rd = rect_rook_dash.collidepoint(mouse_pos)
        rd_bg = (52, 57, 70) if is_hov_rd else (40, 44, 54)
        rd_border = (255, 120, 40) if is_hov_rd else PANEL_BORDER
        pygame.draw.rect(self.screen, rd_bg, rect_rook_dash, border_radius=10)
        pygame.draw.rect(self.screen, rd_border, rect_rook_dash, width=2 if is_hov_rd else 1, border_radius=10)

        rd_title = self.font_header.render("5. Rook Dash", True, (255, 130, 50))
        self.screen.blit(rd_title, (rect_rook_dash.x + 10, rect_rook_dash.y + 12))
        rd_badge = self.font_micro.render("DASHING ROOKS", True, (255, 160, 80))
        self.screen.blit(rd_badge, (rect_rook_dash.x + 10, rect_rook_dash.y + 32))

        rd_lines = [
            "• 2 Rooks, 8 Pawns & King",
            "• Rooks dash in 4 dirs",
            "• Stops at edge or pawns",
            "• Pawns promote to Rooks",
        ]
        for idx, line in enumerate(rd_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_rook_dash.x + 10, rect_rook_dash.y + 52 + idx * 19))

        btn_rd_rect = pygame.Rect(rect_rook_dash.x + 10, rect_rook_dash.bottom - 36, rect_rook_dash.width - 20, 26)
        btn_rd_color = (255, 145, 65) if is_hov_rd else (240, 110, 30)
        pygame.draw.rect(self.screen, btn_rd_color, btn_rd_rect, border_radius=5)
        btn_rd_lbl = self.font_subtitle.render("PLAY [5]", True, (35, 15, 10))
        self.screen.blit(btn_rd_lbl, btn_rd_lbl.get_rect(center=btn_rd_rect.center))

        # 6. Bishop Dash Card
        is_hov_bd = rect_bishop_dash.collidepoint(mouse_pos)
        bd_bg = (52, 57, 70) if is_hov_bd else (40, 44, 54)
        bd_border = (180, 80, 255) if is_hov_bd else PANEL_BORDER
        pygame.draw.rect(self.screen, bd_bg, rect_bishop_dash, border_radius=10)
        pygame.draw.rect(self.screen, bd_border, rect_bishop_dash, width=2 if is_hov_bd else 1, border_radius=10)

        bd_title = self.font_header.render("6. Bishop Dash", True, (185, 95, 255))
        self.screen.blit(bd_title, (rect_bishop_dash.x + 10, rect_bishop_dash.y + 12))
        bd_badge = self.font_micro.render("DASHING BISHOPS", True, (210, 130, 255))
        self.screen.blit(bd_badge, (rect_bishop_dash.x + 10, rect_bishop_dash.y + 32))

        bd_lines = [
            "• 2 Bishops, 8 Pawns & King",
            "• Bishops dash 4 diagonals",
            "• Stops at edge or pawns",
            "• Pawns promote to Bishops",
        ]
        for idx, line in enumerate(bd_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_bishop_dash.x + 10, rect_bishop_dash.y + 52 + idx * 19))

        btn_bd_rect = pygame.Rect(rect_bishop_dash.x + 10, rect_bishop_dash.bottom - 36, rect_bishop_dash.width - 20, 26)
        btn_bd_color = (200, 110, 255) if is_hov_bd else (170, 70, 245)
        pygame.draw.rect(self.screen, btn_bd_color, btn_bd_rect, border_radius=5)
        btn_bd_lbl = self.font_subtitle.render("PLAY [6]", True, (30, 10, 40))
        self.screen.blit(btn_bd_lbl, btn_bd_lbl.get_rect(center=btn_bd_rect.center))

        # ---------------------------------------------------------------------
        # Opponent & Bot Difficulty Section
        # ---------------------------------------------------------------------
        pygame.draw.line(self.screen, (54, 60, 72), (screen_w // 2 - 450, 302 + offset_y), (screen_w // 2 + 450, 302 + offset_y), 1)

        opp_title = self.font_header.render("OPPONENT & BOT DIFFICULTY", True, CYAN_COLOR)
        self.screen.blit(opp_title, opp_title.get_rect(center=(screen_w // 2, 320 + offset_y)))

        vs_bot_r, vs_local_r, diff_rects, side_rects, start_game_r = self.get_mode_selector_ai_rects()
        is_bot_enabled = bool(bot_controller.enabled) if bot_controller else True
        curr_diff = bot_controller.difficulty if bot_controller else BotDifficulty.CASUAL
        curr_side = bot_controller.player_color if bot_controller else chess.WHITE

        # Singleplayer VS AI button
        hov_bot = vs_bot_r.collidepoint(mouse_pos)
        bot_bg = (35, 55, 55) if is_bot_enabled else (BTN_HOVER if hov_bot else BTN_COLOR)
        bot_border = CYAN_COLOR if is_bot_enabled else (ACCENT_COLOR if hov_bot else BTN_BORDER)
        pygame.draw.rect(self.screen, bot_bg, vs_bot_r, border_radius=6)
        pygame.draw.rect(self.screen, bot_border, vs_bot_r, width=2 if is_bot_enabled else 1, border_radius=6)
        bot_lbl_str = "● VS AI BOT (Singleplayer)" if is_bot_enabled else "○ VS AI BOT (Singleplayer)"
        bot_lbl = self.font_small.render(bot_lbl_str, True, CYAN_COLOR if is_bot_enabled else TEXT_PRIMARY)
        self.screen.blit(bot_lbl, bot_lbl.get_rect(center=vs_bot_r.center))

        # 2-Player Local button
        hov_loc = vs_local_r.collidepoint(mouse_pos)
        loc_bg = (40, 50, 65) if not is_bot_enabled else (BTN_HOVER if hov_loc else BTN_COLOR)
        loc_border = GOLD_COLOR if not is_bot_enabled else (ACCENT_COLOR if hov_loc else BTN_BORDER)
        pygame.draw.rect(self.screen, loc_bg, vs_local_r, border_radius=6)
        pygame.draw.rect(self.screen, loc_border, vs_local_r, width=2 if not is_bot_enabled else 1, border_radius=6)
        loc_lbl_str = "● 2-PLAYER LOCAL" if not is_bot_enabled else "○ 2-PLAYER LOCAL"
        loc_lbl = self.font_small.render(loc_lbl_str, True, GOLD_COLOR if not is_bot_enabled else TEXT_SECONDARY)
        self.screen.blit(loc_lbl, loc_lbl.get_rect(center=vs_local_r.center))

        # Side Selection (White, Random, Black)
        w_side_r, r_side_r, b_side_r = side_rects
        side_caption = self.font_micro.render("Play Side:", True, TEXT_MUTED if not is_bot_enabled else TEXT_SECONDARY)
        self.screen.blit(side_caption, (w_side_r.x - 62, w_side_r.centery - 6))

        for s_rect, s_name, is_sel in [
            (w_side_r, "White ♔", is_bot_enabled and curr_side == chess.WHITE),
            (r_side_r, "Random ⚄", False),
            (b_side_r, "Black ♚", is_bot_enabled and curr_side == chess.BLACK),
        ]:
            hov_s = s_rect.collidepoint(mouse_pos)
            s_bg = (38, 55, 48) if is_sel else (BTN_HOVER if hov_s else BTN_COLOR)
            s_border = ACCENT_COLOR if is_sel else (CYAN_COLOR if hov_s else BTN_BORDER)
            pygame.draw.rect(self.screen, s_bg, s_rect, border_radius=5)
            pygame.draw.rect(self.screen, s_border, s_rect, width=2 if is_sel else 1, border_radius=5)
            s_txt = self.font_small.render(s_name, True, ACCENT_COLOR if is_sel else (TEXT_PRIMARY if is_bot_enabled else TEXT_MUTED))
            self.screen.blit(s_txt, s_txt.get_rect(center=s_rect.center))

        # 4 Bot Difficulty Cards
        for d_rect, diff in diff_rects:
            meta = BOT_DIFFICULTY_METADATA[diff]
            is_active_diff = is_bot_enabled and (curr_diff == diff)
            hov_d = d_rect.collidepoint(mouse_pos)
            color_accent = meta["badge_color"]

            if is_active_diff:
                d_bg = (42, 46, 58)
                d_border = color_accent
                bw = 2
            elif hov_d and is_bot_enabled:
                d_bg = BTN_HOVER
                d_border = (120, 130, 150)
                bw = 1
            else:
                d_bg = BTN_COLOR
                d_border = BTN_BORDER
                bw = 1

            pygame.draw.rect(self.screen, d_bg, d_rect, border_radius=8)
            pygame.draw.rect(self.screen, d_border, d_rect, width=bw, border_radius=8)

            # Title & Elo badge
            title_str = f"{meta['level_num']}. {meta['name']}"
            t_surf = self.font_subtitle.render(title_str, True, color_accent if is_active_diff else (TEXT_PRIMARY if is_bot_enabled else TEXT_MUTED))
            self.screen.blit(t_surf, (d_rect.x + 10, d_rect.y + 10))

            elo_surf = self.font_micro.render(meta["elo"], True, color_accent if is_active_diff else TEXT_MUTED)
            self.screen.blit(elo_surf, (d_rect.right - elo_surf.get_width() - 10, d_rect.y + 10))

            desc_surf = self.font_micro.render(meta["desc"], True, TEXT_SECONDARY if is_bot_enabled else TEXT_MUTED)
            self.screen.blit(desc_surf, (d_rect.x + 10, d_rect.y + 32))

        # ---------------------------------------------------------------------
        # Pre-Match Match Timer (Time Control) Section
        # ---------------------------------------------------------------------
        pygame.draw.line(self.screen, (54, 60, 72), (screen_w // 2 - 450, 460 + offset_y), (screen_w // 2 + 450, 460 + offset_y), 1)

        timer_title = self.font_header.render("TIME CONTROL (SET MATCH TIMER)", True, GOLD_COLOR)
        self.screen.blit(timer_title, timer_title.get_rect(center=(screen_w // 2, 476 + offset_y)))

        timer_sub = self.font_micro.render("Choose match time limit before starting. Clock begins ticking on first move.", True, TEXT_MUTED)
        self.screen.blit(timer_sub, timer_sub.get_rect(center=(screen_w // 2, 494 + offset_y)))

        preset_rects, minus_rect, plus_rect = self.get_mode_selector_timer_rects()
        current_limit = timer.time_limit_seconds if timer else 300

        presets_info = [
            ("Unlimited", None),
            ("1 min", 60),
            ("3 min", 180),
            ("5 min", 300),
            ("10 min", 600),
            ("15 min", 900),
            ("30 min", 1800),
        ]

        for (p_rect, _), (label, sec) in zip(preset_rects, presets_info):
            is_selected = (current_limit == sec)
            is_hover = p_rect.collidepoint(mouse_pos)

            if is_selected:
                bg = (38, 70, 55)
                border = ACCENT_COLOR
                txt_color = ACCENT_COLOR
                b_width = 2
            elif is_hover:
                bg = BTN_HOVER
                border = (120, 130, 150)
                txt_color = TEXT_PRIMARY
                b_width = 1
            else:
                bg = BTN_COLOR
                border = BTN_BORDER
                txt_color = TEXT_SECONDARY
                b_width = 1

            pygame.draw.rect(self.screen, bg, p_rect, border_radius=6)
            pygame.draw.rect(self.screen, border, p_rect, width=b_width, border_radius=6)
            p_lbl = self.font_subtitle.render(label, True, txt_color)
            self.screen.blit(p_lbl, p_lbl.get_rect(center=p_rect.center))

        # Custom minute adjuster: [- 1m] [Current: X min] [+ 1m]
        curr_min_str = timer.get_time_preset_label() if timer else "5 min"
        curr_lbl = self.font_small.render(f"Selected: {curr_min_str}", True, TEXT_PRIMARY)
        self.screen.blit(curr_lbl, curr_lbl.get_rect(center=(screen_w // 2 - 18, 565 + offset_y)))

        # Minus button
        is_hov_m = minus_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, BTN_HOVER if is_hov_m else BTN_COLOR, minus_rect, border_radius=5)
        pygame.draw.rect(self.screen, ACCENT_COLOR if is_hov_m else BTN_BORDER, minus_rect, width=1, border_radius=5)
        m_txt = self.font_small.render("-1m", True, TEXT_PRIMARY)
        self.screen.blit(m_txt, m_txt.get_rect(center=minus_rect.center))

        # Plus button
        is_hov_p = plus_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, BTN_HOVER if is_hov_p else BTN_COLOR, plus_rect, border_radius=5)
        pygame.draw.rect(self.screen, ACCENT_COLOR if is_hov_p else BTN_BORDER, plus_rect, width=1, border_radius=5)
        p_txt = self.font_small.render("+1m", True, TEXT_PRIMARY)
        self.screen.blit(p_txt, p_txt.get_rect(center=plus_rect.center))

        # ---------------------------------------------------------------------
        # Start Match Button
        # ---------------------------------------------------------------------
        pygame.draw.line(self.screen, (54, 60, 72), (screen_w // 2 - 450, 590 + offset_y), (screen_w // 2 + 450, 590 + offset_y), 1)

        is_hov_start = start_game_r.collidepoint(mouse_pos)
        start_bg = ACCENT_HOVER if is_hov_start else ACCENT_COLOR
        pygame.draw.rect(self.screen, start_bg, start_game_r, border_radius=8)
        pygame.draw.rect(self.screen, (160, 245, 205) if is_hov_start else (120, 225, 175), start_game_r, width=1, border_radius=8)
        start_lbl = self.font_header.render("START MATCH / PLAY NOW", True, (15, 35, 25))
        self.screen.blit(start_lbl, start_lbl.get_rect(center=start_game_r.center))

        tip_txt = self.font_micro.render("Press [1-6] for mode • [B] cycle bot level • [Space] start • [Esc] resume", True, TEXT_MUTED)
        self.screen.blit(tip_txt, tip_txt.get_rect(center=(screen_w // 2, 656 + offset_y)))

        return rect_classic, rect_uno, rect_snail, rect_queen_pawn, rect_rook_dash, rect_bishop_dash


    # -------------------------------------------------------------------------
    # UNO Card Visual Graphics & Animations
    # -------------------------------------------------------------------------

    def draw_uno_card_graphic(self, card: Any, center_x: int, center_y: int, width: int = 105, height: int = 145) -> None:
        """Render a stylized, authentic UNO card on screen."""
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (center_x, center_y)

        color_rgb = UNO_COLORS.get(card.color.value, (200, 50, 50))

        # Card shadow
        shadow = rect.inflate(6, 6)
        pygame.draw.rect(self.screen, (15, 18, 22), shadow, border_radius=10)

        # White border
        pygame.draw.rect(self.screen, (245, 245, 245), rect, border_radius=8)

        # Card colored body
        body = rect.inflate(-8, -8)
        pygame.draw.rect(self.screen, color_rgb, body, border_radius=6)

        # White center oval
        oval_w = int(body.width * 0.82)
        oval_h = int(body.height * 0.62)
        oval_rect = pygame.Rect(0, 0, oval_w, oval_h)
        oval_rect.center = body.center
        pygame.draw.ellipse(self.screen, (250, 250, 250), oval_rect)

        # Center card symbol
        symbol_str = card.symbol
        use_font = self.font_card_large if len(symbol_str) <= 2 else self.font_card_med
        sym_surf = use_font.render(symbol_str, True, color_rgb)
        s_rect = sym_surf.get_rect(center=oval_rect.center)
        self.screen.blit(sym_surf, s_rect)

        # Corner symbols
        top_left_sym = self.font_card_corner.render(symbol_str, True, (255, 255, 255))
        self.screen.blit(top_left_sym, (body.x + 4, body.y + 4))

        bot_right_sym = self.font_card_corner.render(symbol_str, True, (255, 255, 255))
        b_rect = bot_right_sym.get_rect(right=body.right - 4, bottom=body.bottom - 4)
        self.screen.blit(bot_right_sym, b_rect)

    def draw_uno_card_back(self, center_x: int, center_y: int, width: int = 105, height: int = 145) -> None:
        """Render a realistic, stylized face-down UNO card deck."""
        # 3D Deck stack layers
        for offset in [4, 2]:
            stack_rect = pygame.Rect(0, 0, width, height)
            stack_rect.center = (center_x + offset, center_y + offset)
            pygame.draw.rect(self.screen, (15, 18, 22), stack_rect, border_radius=8)
            pygame.draw.rect(self.screen, (80, 85, 95), stack_rect, width=1, border_radius=8)

        rect = pygame.Rect(0, 0, width, height)
        rect.center = (center_x, center_y)

        # White border
        pygame.draw.rect(self.screen, (245, 245, 245), rect, border_radius=8)

        # Dark charcoal body
        body = rect.inflate(-8, -8)
        pygame.draw.rect(self.screen, (28, 30, 36), body, border_radius=6)

        # Red center tilted oval
        oval_w = int(body.width * 0.82)
        oval_h = int(body.height * 0.55)
        oval_rect = pygame.Rect(0, 0, oval_w, oval_h)
        oval_rect.center = body.center
        pygame.draw.ellipse(self.screen, (220, 48, 48), oval_rect)

        # Bold yellow "UNO" logo
        uno_txt = self.font_card_med.render("UNO", True, (245, 210, 30))
        u_rect = uno_txt.get_rect(center=oval_rect.center)
        self.screen.blit(uno_txt, u_rect)

    def draw_shuffling_animation(
        self,
        center_x: int,
        center_y: int,
        progress: float,
        width: int = 105,
        height: int = 145,
    ) -> None:
        """Render dynamic multi-card shuffling, riffling, and flip reveal animation."""
        fan_colors = [(220, 48, 48), (35, 115, 230), (42, 175, 80), (235, 190, 25)]
        num_cards = 4

        # Riffle fan effect
        for i in range(num_cards):
            phase_offset = i * (math.pi / 2.0)
            shift_x = int(math.sin(progress * math.pi * 6.0 + phase_offset) * (18 - i * 3))
            shift_y = int(math.cos(progress * math.pi * 5.0 + phase_offset) * 4)

            c_rect = pygame.Rect(0, 0, width, height)
            c_rect.center = (center_x + shift_x, center_y + shift_y)

            pygame.draw.rect(self.screen, (15, 18, 22), c_rect.inflate(4, 4), border_radius=8)
            pygame.draw.rect(self.screen, (245, 245, 245), c_rect, border_radius=8)

            c_body = c_rect.inflate(-8, -8)
            card_color = fan_colors[(i + int(progress * 14)) % len(fan_colors)]
            pygame.draw.rect(self.screen, card_color, c_body, border_radius=6)

            ov_w = int(c_body.width * 0.72)
            ov_h = int(c_body.height * 0.48)
            ov_rect = pygame.Rect(0, 0, ov_w, ov_h)
            ov_rect.center = c_body.center
            pygame.draw.ellipse(self.screen, (250, 250, 250), ov_rect)

        # Flipping card in final 25% of progress
        if progress >= 0.75:
            flip_p = (progress - 0.75) / 0.25
            scale_x = abs(math.cos(flip_p * math.pi))
            flip_w = max(4, int(width * scale_x))
            f_rect = pygame.Rect(0, 0, flip_w, height)
            f_rect.center = (center_x, center_y)

            flip_color = (28, 30, 36) if flip_p < 0.5 else (220, 48, 48)
            pygame.draw.rect(self.screen, (245, 245, 245), f_rect, border_radius=8)
            pygame.draw.rect(self.screen, flip_color, f_rect.inflate(-6, -6), border_radius=6)

    # -------------------------------------------------------------------------
    # Right-Hand Information Panel
    # -------------------------------------------------------------------------

    def draw_panel(
        self,
        game_state: GameState,
        active_pack_name: str,
        active_pack_index: int,
        total_packs: int,
        mouse_pos: Tuple[int, int],
        sound_enabled: bool,
        flipped: bool,
        piece_images: Optional[Dict[str, pygame.Surface]] = None,
        timer: Optional[ChessTimer] = None,
        is_fullscreen: bool = False,
        bot_controller: Optional[ChessBotController] = None,
    ) -> None:
        """Render the complete right-hand info panel including clocks, turn status, and modes."""
        panel_rect = pygame.Rect(self.panel_x - 15, 0, self.screen.get_width() - self.panel_x + 15, self.screen.get_height())
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (self.panel_x - 15, 0), (self.panel_x - 15, self.screen.get_height()), 2)

        px = self.panel_x
        pw = self.panel_width

        # 1. Header & Brand
        title = self.font_title.render("CHESSNO", True, TEXT_PRIMARY)
        self.screen.blit(title, (px, 32))

        # Fullscreen & Bot Quick Toggle in Header
        fs_label = "Windowed" if is_fullscreen else "Fullscreen"
        self._draw_button(fs_label, self.buttons.fullscreen, mouse_pos)

        is_uno_mode = (game_state.mode.name == "Chess + UNO")
        is_snail_mode = isinstance(game_state.mode, ImmortalSnailMode)
        is_queen_pawn_mode = (game_state.mode.name in ("Queen Pawn", "Queen Pawn Game"))
        is_rook_dash_mode = (game_state.mode.name == "Rook Dash")
        is_bishop_dash_mode = (game_state.mode.name == "Bishop Dash")
        if is_snail_mode:
            mode_str = "MODE: IMMORTAL SNAIL"
            mode_color = (140, 230, 90)
        elif is_uno_mode:
            mode_str = "MODE: CHESS + UNO"
            mode_color = GOLD_COLOR
        elif is_queen_pawn_mode:
            mode_str = "MODE: QUEEN PAWN"
            mode_color = (245, 105, 180)
        elif is_rook_dash_mode:
            mode_str = "MODE: ROOK DASH"
            mode_color = (255, 120, 40)
        elif is_bishop_dash_mode:
            mode_str = "MODE: BISHOP DASH"
            mode_color = (180, 80, 255)
        else:
            mode_str = "MODE: CLASSIC"
            mode_color = ACCENT_COLOR

        mode_badge = self.font_subtitle.render(mode_str, True, mode_color)
        self.screen.blit(mode_badge, (px, 70))

        # Mode and Timer switcher buttons in header
        self._draw_button("Mode", self.buttons.mode_select, mouse_pos)
        t_label = timer.get_time_preset_label() if timer else "5 min"
        self._draw_button(f"⏱ {t_label}", self.buttons.timer_select, mouse_pos)

        pygame.draw.line(self.screen, PANEL_BORDER, (px, 94), (px + pw, 94), 1)

        # -------------------------------------------------------------
        # Chess Match Clocks (White & Black)
        # -------------------------------------------------------------
        w_rect = self.buttons.white_clock
        b_rect = self.buttons.black_clock

        # Calculate material advantage
        piece_vals = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
        w_mat = sum(len(game_state.board.pieces(pt, chess.WHITE)) * v for pt, v in piece_vals.items())
        b_mat = sum(len(game_state.board.pieces(pt, chess.BLACK)) * v for pt, v in piece_vals.items())
        w_adv = w_mat - b_mat

        # White Clock
        w_running = bool(timer and timer.is_running and game_state.turn == chess.WHITE and not game_state.is_game_over())
        w_low = bool(timer and timer.is_low_time(chess.WHITE))
        w_pulse = int(25 * abs(math.sin(pygame.time.get_ticks() * 0.005))) if w_running else 0
        w_bg = (58, 28, 28) if (w_running and w_low) else ((28, 48, 38) if w_running else PANEL_CARD_BG)
        w_border = CHECK_COLOR if (w_running and w_low) else (
            (min(255, 86 + w_pulse), min(255, 182 + w_pulse), min(255, 139 + w_pulse)) if w_running else PANEL_BORDER
        )

        pygame.draw.rect(self.screen, w_bg, w_rect, border_radius=7)
        pygame.draw.rect(self.screen, w_border, w_rect, width=2 if w_running else 1, border_radius=7)
        pygame.draw.circle(self.screen, (245, 245, 245), (w_rect.x + 12, w_rect.y + 12), 4)
        w_lbl = self.font_micro.render("WHITE", True, TEXT_PRIMARY if w_running else TEXT_MUTED)
        self.screen.blit(w_lbl, (w_rect.x + 20, w_rect.y + 6))
        if w_adv > 0:
            adv_txt = self.font_micro.render(f"+{w_adv}", True, GOLD_COLOR)
            self.screen.blit(adv_txt, (w_rect.right - 28, w_rect.y + 6))

        w_time_str = timer.format_time(timer.white_time) if (timer and timer.has_timer) else "Unlimited"
        w_t_color = (255, 120, 120) if (w_running and w_low) else (TEXT_PRIMARY if w_running else TEXT_SECONDARY)
        w_t_font = self.font_clock if (timer and timer.has_timer) else self.font_small
        w_t_surf = w_t_font.render(w_time_str, True, w_t_color)
        self.screen.blit(w_t_surf, w_t_surf.get_rect(center=(w_rect.centerx, w_rect.y + 29)))

        # Black Clock
        b_running = bool(timer and timer.is_running and game_state.turn == chess.BLACK and not game_state.is_game_over())
        b_low = bool(timer and timer.is_low_time(chess.BLACK))
        b_pulse = int(25 * abs(math.sin(pygame.time.get_ticks() * 0.005))) if b_running else 0
        b_bg = (58, 28, 28) if (b_running and b_low) else ((28, 48, 38) if b_running else PANEL_CARD_BG)
        b_border = CHECK_COLOR if (b_running and b_low) else (
            (min(255, 86 + b_pulse), min(255, 182 + b_pulse), min(255, 139 + b_pulse)) if b_running else PANEL_BORDER
        )

        pygame.draw.rect(self.screen, b_bg, b_rect, border_radius=7)
        pygame.draw.rect(self.screen, b_border, b_rect, width=2 if b_running else 1, border_radius=7)
        pygame.draw.circle(self.screen, (20, 22, 28), (b_rect.x + 12, b_rect.y + 12), 4)
        pygame.draw.circle(self.screen, (100, 105, 120), (b_rect.x + 12, b_rect.y + 12), 4, width=1)
        b_lbl = self.font_micro.render("BLACK", True, TEXT_PRIMARY if b_running else TEXT_MUTED)
        self.screen.blit(b_lbl, (b_rect.x + 20, b_rect.y + 6))
        if w_adv < 0:
            adv_txt = self.font_micro.render(f"+{abs(w_adv)}", True, GOLD_COLOR)
            self.screen.blit(adv_txt, (b_rect.right - 28, b_rect.y + 6))

        b_time_str = timer.format_time(timer.black_time) if (timer and timer.has_timer) else "Unlimited"
        b_t_color = (255, 120, 120) if (b_running and b_low) else (TEXT_PRIMARY if b_running else TEXT_SECONDARY)
        b_t_font = self.font_clock if (timer and timer.has_timer) else self.font_small
        b_t_surf = b_t_font.render(b_time_str, True, b_t_color)
        self.screen.blit(b_t_surf, b_t_surf.get_rect(center=(b_rect.centerx, b_rect.y + 29)))

        # 2. Turn & Status Card
        card_rect = pygame.Rect(px, 154, pw, 78)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, card_rect, width=1, border_radius=8)

        # Check if bot is active
        is_bot_turn = bool(bot_controller and bot_controller.enabled and game_state.turn == bot_controller.bot_color and not game_state.is_game_over())

        # Turn indicator
        if is_bot_turn:
            turn_str = f"BOT ({bot_controller.difficulty.value.upper()})"
            turn_color = bot_controller.current_metadata["badge_color"]
        elif bot_controller and bot_controller.enabled:
            turn_str = f"YOUR TURN ({game_state.turn_name.upper()})"
            turn_color = TEXT_PRIMARY
        else:
            if is_uno_mode and hasattr(game_state.mode, "player_sides"):
                p1_color = game_state.mode.player_sides.get("Player 1", chess.WHITE)
                curr_p = "Player 1" if game_state.turn == p1_color else "Player 2"
                turn_str = f"{curr_p.upper()} ({game_state.turn_name.upper()})"
            else:
                turn_str = "WHITE TO MOVE" if game_state.turn == chess.WHITE else "BLACK TO MOVE"
            turn_color = TEXT_PRIMARY if game_state.turn == chess.WHITE else (210, 215, 225)

        indicator_bg = (240, 240, 240) if game_state.turn == chess.WHITE else (30, 32, 40)
        indicator_border = (200, 200, 200) if game_state.turn == chess.WHITE else (100, 105, 120)

        pygame.draw.circle(self.screen, indicator_bg, (px + 22, 172), 9)
        pygame.draw.circle(self.screen, indicator_border, (px + 22, 172), 9, width=2)

        turn_lbl = self.font_header.render(turn_str, True, turn_color)
        self.screen.blit(turn_lbl, (px + 40, 163))

        # Status badge
        status_text = game_state.status_summary()
        if game_state.is_game_over():
            badge_color = GOLD_COLOR
            badge_bg = (70, 60, 25)
        elif game_state.is_in_check():
            badge_color = CHECK_COLOR
            badge_bg = (70, 30, 30)
        elif is_bot_turn and bot_controller and bot_controller.is_thinking:
            meta = bot_controller.current_metadata
            badge_color = meta["badge_color"]
            badge_bg = (30, 48, 45)
            dots = "." * (1 + (int(pygame.time.get_ticks() / 250) % 3))
            status_text = f"Bot Thinking{dots} ({meta['name']})"
        elif is_uno_mode and hasattr(game_state.mode, "current_card") and game_state.mode.current_card and game_state.mode.current_card.card_type.value == "Reverse":
            badge_color = CYAN_COLOR
            badge_bg = (20, 50, 60)
            status_text = "REVERSE: Sides Swapped!"
        elif is_uno_mode and hasattr(game_state.mode, "phase") and game_state.mode.phase.value == "Awaiting Draw":
            badge_color = GOLD_COLOR
            badge_bg = (60, 52, 25)
            status_text = "Action: Draw UNO Card"
        elif is_uno_mode and hasattr(game_state.mode, "moves_remaining") and game_state.mode.moves_remaining > 1:
            badge_color = GOLD_COLOR
            badge_bg = (60, 52, 25)
            status_text = f"Multi-Move: {game_state.mode.moves_remaining} left"
        elif is_snail_mode:
            badge_color = (140, 230, 90)
            badge_bg = (30, 55, 30)
            step_rem = game_state.mode.moves_until_next_step
            status_text = f"Snail steps in {step_rem} move{'s' if step_rem > 1 else ''}"
        else:
            badge_color = ACCENT_COLOR
            badge_bg = (25, 55, 40)

        status_rect = pygame.Rect(px + 12, 194, pw - 24, 28)
        pygame.draw.rect(self.screen, badge_bg, status_rect, border_radius=6)
        pygame.draw.rect(self.screen, badge_color, status_rect, width=1, border_radius=6)

        status_lbl = self.font_small.render(status_text, True, badge_color)
        lbl_rect = status_lbl.get_rect(center=status_rect.center)
        self.screen.blit(status_lbl, lbl_rect)

        # 3. Game Stats / History Card
        stats_rect = pygame.Rect(px, 240, pw, 58)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, stats_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, stats_rect, width=1, border_radius=8)

        move_num = game_state.fullmove_number
        last_san = game_state.move_history[-1].san if game_state.move_history else "-"
        
        stat1 = self.font_small.render(f"Move: {move_num}", True, TEXT_SECONDARY)
        stat2 = self.font_small.render(f"Last Move: {last_san}", True, ACCENT_COLOR)
        self.screen.blit(stat1, (px + 14, 248))
        self.screen.blit(stat2, (px + 14, 270))

        # 4. Theme Selection Section
        theme_lbl = self.font_subtitle.render("PIECE & BOARD THEME", True, TEXT_MUTED)
        self.screen.blit(theme_lbl, (px, 308))

        pack_info = f"{active_pack_name} ({active_pack_index + 1}/{total_packs})"
        pack_text = self.font_small.render(pack_info, True, TEXT_PRIMARY)
        pack_rect = pack_text.get_rect(centerx=px + pw // 2, centery=344)
        self.screen.blit(pack_text, pack_rect)

        self._draw_button("< Prev", self.buttons.prev_theme, mouse_pos)
        self._draw_button("Next >", self.buttons.next_theme, mouse_pos)

        # 5. Action Buttons (New Game, Flip, Sound)
        self._draw_button("New Game (Restart)", self.buttons.new_game, mouse_pos, accent=True)
        flip_text = "View: Black" if flipped else "View: White"
        self._draw_button(flip_text, self.buttons.flip_board, mouse_pos)
        sound_text = "Sound: ON" if sound_enabled else "Sound: OFF"
        self._draw_button(sound_text, self.buttons.sound_toggle, mouse_pos)

        # AI Bot Control Buttons
        if bot_controller is not None:
            bot_btn_text = "VS Bot: ON" if bot_controller.enabled else "VS Bot: OFF"
            self._draw_button(bot_btn_text, self.buttons.bot_toggle, mouse_pos, accent=bot_controller.enabled)
            diff_btn_text = f"Bot: {bot_controller.difficulty.value}"
            self._draw_button(diff_btn_text, self.buttons.bot_difficulty, mouse_pos)

        # 6. Active Mode Section: UNO Cards or Classic Placeholder
        mod_rect = pygame.Rect(px, 466, pw, 272)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, mod_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, mod_rect, width=1, border_radius=8)

        if is_uno_mode and hasattr(game_state.mode, "phase"):
            mode = game_state.mode
            deck = mode.deck
            phase_val = mode.phase.value

            card_cx = px + pw // 2
            card_cy = 530

            # STATE 1: Awaiting Draw (Button + Deck)
            if phase_val == "Awaiting Draw":
                self.draw_uno_card_back(card_cx, card_cy, width=100, height=132)
                self._draw_button("Draw Card", self.buttons.draw_card, mouse_pos, accent=True)

                hint_str = "Click button or press [Space]"
                h_surf = self.font_micro.render(hint_str, True, (240, 205, 80))
                self.screen.blit(h_surf, h_surf.get_rect(center=(px + pw // 2, 692)))

            # STATE 2: Shuffling animation in progress
            elif phase_val == "Shuffling":
                self.draw_shuffling_animation(card_cx, card_cy, mode.shuffle_progress, width=100, height=132)

                dots = "." * (1 + (int(pygame.time.get_ticks() / 150) % 3))
                shuff_str = f"Shuffling Deck{dots}"
                s_surf = self.font_subtitle.render(shuff_str, True, GOLD_COLOR)
                self.screen.blit(s_surf, s_surf.get_rect(center=(px + pw // 2, 626)))

                deck_str = f"Deck: {deck.draw_pile_count} left"
                d_surf = self.font_micro.render(deck_str, True, TEXT_SECONDARY)
                self.screen.blit(d_surf, d_surf.get_rect(center=(px + pw // 2, 650)))

            # STATE 3: Card is revealed and active
            else:
                card = mode.current_card
                if card is not None:
                    self.draw_uno_card_graphic(card, card_cx, card_cy, width=100, height=132)

                    rem = mode.moves_remaining
                    tot = mode.moves_allowed
                    move_info_str = f"Moves: {tot - rem + 1} of {tot}"
                    m_surf = self.font_subtitle.render(move_info_str, True, GOLD_COLOR)
                    self.screen.blit(m_surf, m_surf.get_rect(center=(px + pw // 2, 622)))

                    deck_str = f"Deck: {deck.draw_pile_count} left | Discard: {deck.discard_pile_count}"
                    d_surf = self.font_micro.render(deck_str, True, TEXT_SECONDARY)
                    self.screen.blit(d_surf, d_surf.get_rect(center=(px + pw // 2, 644)))

                    if mode.skip_alert_message:
                        alert_surf = self.font_micro.render(mode.skip_alert_message, True, CHECK_COLOR)
                        self.screen.blit(alert_surf, alert_surf.get_rect(center=(px + pw // 2, 668)))
                    elif mode.pending_skips > 0:
                        skip_surf = self.font_micro.render(f"Pending Skips: {mode.pending_skips}", True, (240, 160, 50))
                        self.screen.blit(skip_surf, skip_surf.get_rect(center=(px + pw // 2, 668)))
                    else:
                        desc_surf = self.font_micro.render(card.description, True, TEXT_MUTED)
                        self.screen.blit(desc_surf, desc_surf.get_rect(center=(px + pw // 2, 668)))

        elif is_snail_mode:
            mode = game_state.mode
            mod_title = self.font_subtitle.render("DUAL IMMORTAL SNAILS", True, (140, 230, 90))
            self.screen.blit(mod_title, (px + 14, 466))

            rem_moves = mode.moves_until_next_step
            step_lbl = self.font_small.render("Next step:", True, TEXT_PRIMARY)
            self.screen.blit(step_lbl, (px + 14, 486))

            pip_w = 22
            pip_h = 13
            pip_start_x = px + 88
            for p in range(5):
                pip_rect = pygame.Rect(pip_start_x + p * (pip_w + 4), 488, pip_w, pip_h)
                filled = (p < (5 - rem_moves))
                if filled:
                    pygame.draw.rect(self.screen, (140, 220, 80), pip_rect, border_radius=3)
                else:
                    pygame.draw.rect(self.screen, (50, 56, 68), pip_rect, border_radius=3)
                    pygame.draw.rect(self.screen, (75, 82, 98), pip_rect, width=1, border_radius=3)

            count_desc = f"{rem_moves} legal move{'s' if rem_moves > 1 else ''} until step"
            desc_surf = self.font_micro.render(count_desc, True, (140, 220, 80) if rem_moves == 1 else TEXT_MUTED)
            self.screen.blit(desc_surf, (px + 14, 504))

            # White Snail Info Card
            w_snail = mode.white_snail
            w_dist = w_snail.distance_to_target(game_state)
            w_dist_str = f"{w_dist} tiles" if w_dist is not None else "N/A"
            w_card_rect = pygame.Rect(px + 10, 522, pw - 20, 50)
            pygame.draw.rect(self.screen, (34, 46, 42), w_card_rect, border_radius=6)
            pygame.draw.rect(self.screen, (90, 215, 185), w_card_rect, width=1, border_radius=6)

            w_title = self.font_micro.render(f"WHITE SNAIL [{w_snail.location_name}]", True, (140, 255, 230))
            w_sub1 = self.font_micro.render(f"Hunting Black King ({w_dist_str} away)", True, TEXT_PRIMARY)
            w_sub2 = self.font_micro.render(f"Crushed: {len(w_snail.crushed_pieces)} Black pieces", True, TEXT_MUTED)
            self.screen.blit(w_title, (px + 16, 525))
            self.screen.blit(w_sub1, (px + 16, 540))
            self.screen.blit(w_sub2, (px + 16, 555))

            # Black Snail Info Card
            b_snail = mode.black_snail
            b_dist = b_snail.distance_to_target(game_state)
            b_dist_str = f"{b_dist} tiles" if b_dist is not None else "N/A"
            b_card_rect = pygame.Rect(px + 10, 576, pw - 20, 50)
            pygame.draw.rect(self.screen, (46, 34, 38), b_card_rect, border_radius=6)
            pygame.draw.rect(self.screen, (240, 95, 95), b_card_rect, width=1, border_radius=6)

            b_title = self.font_micro.render(f"BLACK SNAIL [{b_snail.location_name}]", True, (255, 140, 140))
            b_sub1 = self.font_micro.render(f"Hunting White King ({b_dist_str} away)", True, TEXT_PRIMARY)
            b_sub2 = self.font_micro.render(f"Crushed: {len(b_snail.crushed_pieces)} White pieces", True, TEXT_MUTED)
            self.screen.blit(b_title, (px + 16, 579))
            self.screen.blit(b_sub1, (px + 16, 594))
            self.screen.blit(b_sub2, (px + 16, 609))

            # Alert or Victory
            if mode.target_caught:
                win_rect = pygame.Rect(px + 10, 632, pw - 20, 30)
                pygame.draw.rect(self.screen, (70, 25, 25), win_rect, border_radius=6)
                pygame.draw.rect(self.screen, CHECK_COLOR, win_rect, width=2, border_radius=6)
                vic_msg = "WHITE SNAIL CAUGHT BLACK KING!" if w_snail.target_caught else "BLACK SNAIL CAUGHT WHITE KING!"
                w_title = self.font_micro.render(vic_msg, True, CHECK_COLOR)
                self.screen.blit(w_title, w_title.get_rect(center=win_rect.center))
            else:
                steps_txt = f"Total steps taken: {mode.steps_taken}"
                s_surf = self.font_micro.render(steps_txt, True, TEXT_MUTED)
                self.screen.blit(s_surf, s_surf.get_rect(center=(px + pw // 2, 646)))

        elif is_queen_pawn_mode:
            # Queen Pawn Game HUD
            mod_title = self.font_subtitle.render("QUEEN PAWN BATTLE", True, (245, 105, 180))
            self.screen.blit(mod_title, (px + 14, 466))

            badge_lbl = self.font_micro.render("PAWN ELIMINATION RULES", True, TEXT_MUTED)
            self.screen.blit(badge_lbl, (px + 14, 484))

            # Roster Status Box
            roster_box = pygame.Rect(px + 10, 500, pw - 20, 80)
            pygame.draw.rect(self.screen, (28, 32, 40), roster_box, border_radius=6)
            pygame.draw.rect(self.screen, (100, 60, 90), roster_box, width=1, border_radius=6)

            w_q_sq = list(game_state.board.pieces(chess.QUEEN, chess.WHITE))
            b_q_sq = list(game_state.board.pieces(chess.QUEEN, chess.BLACK))
            w_p_count = len(list(game_state.board.pieces(chess.PAWN, chess.WHITE)))
            b_p_count = len(list(game_state.board.pieces(chess.PAWN, chess.BLACK)))

            w_q_pos = chess.square_name(w_q_sq[0]).upper() if w_q_sq else "DEAD"
            b_q_pos = chess.square_name(b_q_sq[0]).upper() if b_q_sq else "DEAD"

            w_danger = any(game_state.board.is_attacked_by(chess.BLACK, sq) for sq in w_q_sq)
            b_danger = any(game_state.board.is_attacked_by(chess.WHITE, sq) for sq in b_q_sq)

            w_stat_color = (255, 90, 90) if w_danger else ((240, 240, 240) if w_q_sq else TEXT_MUTED)
            b_stat_color = (255, 90, 90) if b_danger else ((240, 240, 240) if b_q_sq else TEXT_MUTED)

            w_txt = f"White Q: {w_q_pos}{' [DANGER!]' if w_danger else ''} | {w_p_count} Pawns"
            b_txt = f"Black Q: {b_q_pos}{' [DANGER!]' if b_danger else ''} | {b_p_count} Pawns"

            t1 = self.font_micro.render(w_txt, True, w_stat_color)
            t2 = self.font_micro.render(b_txt, True, b_stat_color)
            self.screen.blit(t1, (roster_box.x + 10, roster_box.y + 10))
            self.screen.blit(t2, (roster_box.x + 10, roster_box.y + 32))

            obj_txt = self.font_micro.render("Win: Capture all pawns! Tie if only Queens", True, (245, 185, 110))
            self.screen.blit(obj_txt, (roster_box.x + 10, roster_box.y + 54))

            # Captured Pieces Box
            caps_box = pygame.Rect(px + 10, 586, pw - 20, 90)
            pygame.draw.rect(self.screen, (28, 32, 40), caps_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, caps_box, width=1, border_radius=6)

            white_caps = game_state.captured_pieces.get("w", [])
            black_caps = game_state.captured_pieces.get("b", [])

            c_title = self.font_micro.render("CAPTURED PIECES", True, TEXT_MUTED)
            self.screen.blit(c_title, (caps_box.x + 10, caps_box.y + 6))

            w_lbl = self.font_micro.render(f"White (+{len(white_caps)}):", True, TEXT_PRIMARY)
            self.screen.blit(w_lbl, (caps_box.x + 10, caps_box.y + 24))
            if piece_images:
                for i, code in enumerate(white_caps[:8]):
                    if code in piece_images:
                        icon = pygame.transform.smoothscale(piece_images[code], (18, 18))
                        self.screen.blit(icon, (caps_box.x + 85 + i * 18, caps_box.y + 22))
            else:
                codes_str = ", ".join(c.upper() for c in white_caps[:6])
                self.screen.blit(self.font_micro.render(codes_str, True, TEXT_SECONDARY), (caps_box.x + 85, caps_box.y + 24))

            b_lbl = self.font_micro.render(f"Black (+{len(black_caps)}):", True, TEXT_PRIMARY)
            self.screen.blit(b_lbl, (caps_box.x + 10, caps_box.y + 52))
            if piece_images:
                for i, code in enumerate(black_caps[:8]):
                    if code in piece_images:
                        icon = pygame.transform.smoothscale(piece_images[code], (18, 18))
                        self.screen.blit(icon, (caps_box.x + 85 + i * 18, caps_box.y + 50))
            else:
                codes_str = ", ".join(c.upper() for c in black_caps[:6])
                self.screen.blit(self.font_micro.render(codes_str, True, TEXT_SECONDARY), (caps_box.x + 85, caps_box.y + 52))

        elif is_rook_dash_mode:
            # Rook Dash Mode Overview
            mod_title = self.font_subtitle.render("ROOK DASH ARENA", True, (255, 120, 40))
            self.screen.blit(mod_title, (px + 14, 466))

            badge_lbl = self.font_micro.render("4-WAY DASHING ROOKS • CHECKMATE TO WIN", True, (255, 160, 80))
            self.screen.blit(badge_lbl, (px + 14, 484))

            # Rules Card
            rules_box = pygame.Rect(px + 10, 500, pw - 20, 76)
            pygame.draw.rect(self.screen, (28, 32, 40), rules_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, rules_box, width=1, border_radius=6)

            rules = [
                "• Rooks dash in 4 directions",
                "• Stops at board edge or own pawns",
                "• Captures first enemy piece hit",
                "• Pawns promote strictly to Rooks",
            ]
            for idx, rule in enumerate(rules):
                r_txt = self.font_micro.render(rule, True, TEXT_SECONDARY)
                self.screen.blit(r_txt, (rules_box.x + 10, rules_box.y + 6 + idx * 17))

            # Material & Status Card
            caps_box = pygame.Rect(px + 10, 582, pw - 20, 94)
            pygame.draw.rect(self.screen, (28, 32, 40), caps_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, caps_box, width=1, border_radius=6)

            c_title = self.font_micro.render("ACTIVE PIECES & CAPTURES", True, TEXT_MUTED)
            self.screen.blit(c_title, (caps_box.x + 10, caps_box.y + 6))

            white_rooks = len(game_state.board.pieces(chess.ROOK, chess.WHITE))
            white_pawns = len(game_state.board.pieces(chess.PAWN, chess.WHITE))
            black_rooks = len(game_state.board.pieces(chess.ROOK, chess.BLACK))
            black_pawns = len(game_state.board.pieces(chess.PAWN, chess.BLACK))

            w_stat = f"White: {white_rooks} Rooks, {white_pawns} Pawns"
            b_stat = f"Black: {black_rooks} Rooks, {black_pawns} Pawns"
            self.screen.blit(self.font_micro.render(w_stat, True, TEXT_PRIMARY), (caps_box.x + 10, caps_box.y + 24))
            self.screen.blit(self.font_micro.render(b_stat, True, TEXT_PRIMARY), (caps_box.x + 10, caps_box.y + 44))

            white_caps = game_state.captured_pieces.get("w", [])
            black_caps = game_state.captured_pieces.get("b", [])
            cap_stat = f"Captures: W +{len(white_caps)} | B +{len(black_caps)}"
            self.screen.blit(self.font_micro.render(cap_stat, True, (255, 160, 80)), (caps_box.x + 10, caps_box.y + 68))

        elif is_bishop_dash_mode:
            # Bishop Dash Mode Overview
            mod_title = self.font_subtitle.render("BISHOP DASH ARENA", True, (180, 80, 255))
            self.screen.blit(mod_title, (px + 14, 466))

            badge_lbl = self.font_micro.render("4-WAY DIAGONAL DASH • CHECKMATE TO WIN", True, (210, 130, 255))
            self.screen.blit(badge_lbl, (px + 14, 484))

            # Rules Card
            rules_box = pygame.Rect(px + 10, 500, pw - 20, 76)
            pygame.draw.rect(self.screen, (28, 32, 40), rules_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, rules_box, width=1, border_radius=6)

            rules = [
                "• Bishops dash along diagonals",
                "• Stops at board edge or own pawns",
                "• Captures first enemy piece hit",
                "• Pawns promote strictly to Bishops",
            ]
            for idx, rule in enumerate(rules):
                r_txt = self.font_micro.render(rule, True, TEXT_SECONDARY)
                self.screen.blit(r_txt, (rules_box.x + 10, rules_box.y + 6 + idx * 17))

            # Material & Status Card
            caps_box = pygame.Rect(px + 10, 582, pw - 20, 94)
            pygame.draw.rect(self.screen, (28, 32, 40), caps_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, caps_box, width=1, border_radius=6)

            c_title = self.font_micro.render("ACTIVE PIECES & CAPTURES", True, TEXT_MUTED)
            self.screen.blit(c_title, (caps_box.x + 10, caps_box.y + 6))

            white_bishops = len(game_state.board.pieces(chess.BISHOP, chess.WHITE))
            white_pawns = len(game_state.board.pieces(chess.PAWN, chess.WHITE))
            black_bishops = len(game_state.board.pieces(chess.BISHOP, chess.BLACK))
            black_pawns = len(game_state.board.pieces(chess.PAWN, chess.BLACK))

            w_stat = f"White: {white_bishops} Bishops, {white_pawns} Pawns"
            b_stat = f"Black: {black_bishops} Bishops, {black_pawns} Pawns"
            self.screen.blit(self.font_micro.render(w_stat, True, TEXT_PRIMARY), (caps_box.x + 10, caps_box.y + 24))
            self.screen.blit(self.font_micro.render(b_stat, True, TEXT_PRIMARY), (caps_box.x + 10, caps_box.y + 44))

            white_caps = game_state.captured_pieces.get("w", [])
            black_caps = game_state.captured_pieces.get("b", [])
            cap_stat = f"Captures: W +{len(white_caps)} | B +{len(black_caps)}"
            self.screen.blit(self.font_micro.render(cap_stat, True, (210, 130, 255)), (caps_box.x + 10, caps_box.y + 68))

        else:
            # Classic Mode Overview (Standard FIDE Chess)
            mod_title = self.font_subtitle.render("CLASSIC CHESS", True, ACCENT_COLOR)
            self.screen.blit(mod_title, (px + 14, 466))

            badge_lbl = self.font_micro.render("STANDARD FIDE RULES", True, TEXT_MUTED)
            self.screen.blit(badge_lbl, (px + 14, 484))

            # Rules Card
            rules_box = pygame.Rect(px + 10, 500, pw - 20, 76)
            pygame.draw.rect(self.screen, (28, 32, 40), rules_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, rules_box, width=1, border_radius=6)

            rules = [
                "• 2-Player turn-based chess",
                "• Castling & En Passant enabled",
                "• Interactive Pawn Promotion",
                "• Check, Checkmate & Draws",
            ]
            for idx, rule in enumerate(rules):
                r_txt = self.font_micro.render(rule, True, TEXT_SECONDARY)
                self.screen.blit(r_txt, (rules_box.x + 10, rules_box.y + 6 + idx * 17))

            # Material & Captured Pieces Card
            caps_box = pygame.Rect(px + 10, 582, pw - 20, 94)
            pygame.draw.rect(self.screen, (28, 32, 40), caps_box, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_BORDER, caps_box, width=1, border_radius=6)

            white_caps = game_state.captured_pieces.get("w", [])
            black_caps = game_state.captured_pieces.get("b", [])

            if white_caps or black_caps:
                c_title = self.font_micro.render("CAPTURED PIECES", True, TEXT_MUTED)
                self.screen.blit(c_title, (caps_box.x + 10, caps_box.y + 6))

                # Render White's captures (Black pieces)
                w_lbl = self.font_micro.render(f"White (+{len(white_caps)}):", True, TEXT_PRIMARY)
                self.screen.blit(w_lbl, (caps_box.x + 10, caps_box.y + 24))

                if piece_images:
                    for i, code in enumerate(white_caps[:8]):
                        if code in piece_images:
                            icon = pygame.transform.smoothscale(piece_images[code], (18, 18))
                            self.screen.blit(icon, (caps_box.x + 85 + i * 18, caps_box.y + 22))
                    if len(white_caps) > 8:
                        extra_txt = self.font_micro.render(f"+{len(white_caps) - 8}", True, TEXT_MUTED)
                        self.screen.blit(extra_txt, (caps_box.x + 85 + 8 * 18, caps_box.y + 24))
                else:
                    codes_str = ", ".join(c.upper() for c in white_caps[:6])
                    c_surf = self.font_micro.render(codes_str, True, TEXT_SECONDARY)
                    self.screen.blit(c_surf, (caps_box.x + 85, caps_box.y + 24))

                # Render Black's captures (White pieces)
                b_lbl = self.font_micro.render(f"Black (+{len(black_caps)}):", True, TEXT_PRIMARY)
                self.screen.blit(b_lbl, (caps_box.x + 10, caps_box.y + 52))

                if piece_images:
                    for i, code in enumerate(black_caps[:8]):
                        if code in piece_images:
                            icon = pygame.transform.smoothscale(piece_images[code], (18, 18))
                            self.screen.blit(icon, (caps_box.x + 85 + i * 18, caps_box.y + 50))
                    if len(black_caps) > 8:
                        extra_txt = self.font_micro.render(f"+{len(black_caps) - 8}", True, TEXT_MUTED)
                        self.screen.blit(extra_txt, (caps_box.x + 85 + 8 * 18, caps_box.y + 52))
                else:
                    codes_str = ", ".join(c.upper() for c in black_caps[:6])
                    c_surf = self.font_micro.render(codes_str, True, TEXT_SECONDARY)
                    self.screen.blit(c_surf, (caps_box.x + 85, caps_box.y + 52))

                hint_str = "Switch mode anytime via [Mode]"
                h_surf = self.font_micro.render(hint_str, True, TEXT_MUTED)
                self.screen.blit(h_surf, h_surf.get_rect(center=(caps_box.centerx, caps_box.bottom - 10)))
            else:
                c_title = self.font_micro.render("GAME IN PROGRESS", True, TEXT_MUTED)
                self.screen.blit(c_title, (caps_box.x + 10, caps_box.y + 8))

                no_caps_txt = self.font_small.render("No captures yet", True, TEXT_SECONDARY)
                self.screen.blit(no_caps_txt, (caps_box.x + 10, caps_box.y + 26))

                hint1 = self.font_micro.render("Play classic chess, or click", True, TEXT_MUTED)
                hint2 = self.font_micro.render("'Mode' at top for UNO / Snail!", True, GOLD_COLOR)
                self.screen.blit(hint1, (caps_box.x + 10, caps_box.y + 48))
                self.screen.blit(hint2, (caps_box.x + 10, caps_box.y + 66))

        # 7. Quick Controls Footer
        pygame.draw.line(self.screen, PANEL_BORDER, (px, 746), (px + pw, 746), 1)
        help_title = self.font_subtitle.render("CONTROLS", True, TEXT_MUTED)
        self.screen.blit(help_title, (px, 754))

        if is_uno_mode:
            fourth_line = "• [Space] Draw Card"
        elif is_snail_mode:
            fourth_line = "• Snails step every 5 moves"
        else:
            fourth_line = "• [Left / Right] Switch Theme"

        controls = [
            "• Click piece or drag-and-drop",
            "• [B] Cycle Bot Level / AI Mode",
            "• [F11] Fullscreen | [F] Flip View",
            "• [R] Restart | [T] Time | [M] Sound",
            fourth_line,
        ]
        for idx, line in enumerate(controls):
            ctrl_txt = self.font_micro.render(line, True, TEXT_SECONDARY)
            self.screen.blit(ctrl_txt, (px, 774 + idx * 17))

    def _draw_button(
        self,
        text: str,
        rect: pygame.Rect,
        mouse_pos: Tuple[int, int],
        accent: bool = False,
    ) -> None:
        """Utility to draw sleek, styled interactive buttons."""
        hovered = rect.collidepoint(mouse_pos)

        if accent:
            color = ACCENT_HOVER if hovered else ACCENT_COLOR
            border_color = (140, 235, 195) if hovered else (110, 215, 165)
            text_color = (12, 30, 20)
        else:
            color = BTN_HOVER if hovered else BTN_COLOR
            border_color = (125, 138, 165) if hovered else BTN_BORDER
            text_color = TEXT_PRIMARY

        # Subtle shadow when hovered
        if hovered:
            pygame.draw.rect(self.screen, (10, 12, 16), rect.move(0, 1), border_radius=6)

        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, border_color, rect, width=1, border_radius=6)

        label = self.font_small.render(text, True, text_color)
        label_rect = label.get_rect(center=rect.center)
        self.screen.blit(label, label_rect)
