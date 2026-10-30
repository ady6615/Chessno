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
        
        # Mode, Timer, and Fullscreen selector buttons in header
        self.fullscreen = pygame.Rect(panel_x + panel_width - 86, 28, 86, 26)
        self.mode_select = pygame.Rect(panel_x + panel_width - 176, 64, 76, 26)
        self.timer_select = pygame.Rect(panel_x + panel_width - 94, 64, 94, 26)

        # Chess Clocks
        clock_w = (panel_width - 8) // 2
        self.white_clock = pygame.Rect(panel_x, 100, clock_w, 46)
        self.black_clock = pygame.Rect(panel_x + clock_w + 8, 100, clock_w, 46)

        # Theme switching buttons
        self.prev_theme = pygame.Rect(panel_x, 328, 65, 32)
        self.next_theme = pygame.Rect(panel_x + panel_width - 65, 328, 65, 32)
        
        # Action buttons
        self.new_game = pygame.Rect(panel_x, 372, panel_width, 34)
        self.flip_board = pygame.Rect(panel_x, 414, (panel_width - 10) // 2, 32)
        self.sound_toggle = pygame.Rect(panel_x + (panel_width - 10) // 2 + 10, 414, (panel_width - 10) // 2, 32)

        # UNO Interactive Buttons
        self.draw_card = pygame.Rect(panel_x + 14, 638, panel_width - 28, 40)
        self.deck_card = pygame.Rect(panel_x + (panel_width - 105) // 2, 478, 105, 145)

        # Immortal Snail Target Selection Buttons
        btn_w = (panel_width - 34) // 2
        self.target_white = pygame.Rect(panel_x + 14, 510, btn_w, 28)
        self.target_black = pygame.Rect(panel_x + 14 + btn_w + 6, 510, btn_w, 28)


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

        # 3. Blit the board background
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
    ) -> None:
        """
        Draw all chess pieces currently on the board.
        If a piece is being dragged, it is rendered at its square with transparency or suppressed.
        """
        for sq in chess.SQUARES:
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
                self.screen.blit(image, draw_pos)

    def draw_dragged_piece(
        self,
        piece_images: Dict[str, pygame.Surface],
        piece_code: str,
        mouse_pos: Tuple[int, int],
    ) -> None:
        """Render the floating piece sprite directly centered on the mouse cursor."""
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

    def get_mode_selector_rects(self) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """Return clickable rectangles for (Classic, UNO, Snail, Queen_Pawn)."""
        screen_w = self.screen.get_width()
        card_w, card_h = 216, 258
        gap = 14
        total_w = card_w * 4 + gap * 3
        start_x = (screen_w - total_w) // 2
        card_y = 195

        rect_classic = pygame.Rect(start_x, card_y, card_w, card_h)
        rect_uno = pygame.Rect(start_x + card_w + gap, card_y, card_w, card_h)
        rect_snail = pygame.Rect(start_x + (card_w + gap) * 2, card_y, card_w, card_h)
        rect_queen_pawn = pygame.Rect(start_x + (card_w + gap) * 3, card_y, card_w, card_h)
        return rect_classic, rect_uno, rect_snail, rect_queen_pawn

    def get_mode_selector_timer_rects(self) -> Tuple[List[Tuple[pygame.Rect, Optional[int]]], pygame.Rect, pygame.Rect]:
        """Return preset rects [(rect, seconds), ...] and (minus_rect, plus_rect) for the start modal."""
        screen_w = self.screen.get_width()
        presets = [
            ("Unlimited", None),
            ("1 min", 60),
            ("3 min", 180),
            ("5 min", 300),
            ("10 min", 600),
            ("15 min", 900),
            ("30 min", 1800),
        ]
        btn_w, btn_h = 94, 32
        gap = 10
        total_w = len(presets) * btn_w + (len(presets) - 1) * gap
        start_x = (screen_w - total_w) // 2
        y = 545

        preset_rects = []
        for i, (_, sec) in enumerate(presets):
            r = pygame.Rect(start_x + i * (btn_w + gap), y, btn_w, btn_h)
            preset_rects.append((r, sec))

        minus_rect = pygame.Rect(screen_w // 2 - 96, 595, 38, 28)
        plus_rect = pygame.Rect(screen_w // 2 + 58, 595, 38, 28)
        return preset_rects, minus_rect, plus_rect

    def draw_mode_selector_modal(
        self, mouse_pos: Tuple[int, int], timer: Optional[ChessTimer] = None
    ) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """
        Draw a modal start menu allowing the player to select the game mode and match timer.
        Returns the four card Rects for event collision checking.
        """
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((12, 14, 18, 230))
        self.screen.blit(overlay, (0, 0))

        title_y = 115
        title_surf = self.font_title.render("SELECT GAME MODE & TIMER", True, TEXT_PRIMARY)
        t_rect = title_surf.get_rect(center=(screen_w // 2, title_y))
        self.screen.blit(title_surf, t_rect)

        sub_surf = self.font_normal.render("Choose a game mode [1, 2, 3, 4] and set match time before starting", True, TEXT_SECONDARY)
        s_rect = sub_surf.get_rect(center=(screen_w // 2, title_y + 34))
        self.screen.blit(sub_surf, s_rect)

        rect_classic, rect_uno, rect_snail, rect_queen_pawn = self.get_mode_selector_rects()

        # 1. Classic Chess Card
        is_hov_c = rect_classic.collidepoint(mouse_pos)
        c_bg = (52, 57, 70) if is_hov_c else (40, 44, 54)
        c_border = ACCENT_COLOR if is_hov_c else PANEL_BORDER
        pygame.draw.rect(self.screen, c_bg, rect_classic, border_radius=12)
        pygame.draw.rect(self.screen, c_border, rect_classic, width=2 if is_hov_c else 1, border_radius=12)

        c_title = self.font_header.render("1. Classic Chess", True, TEXT_PRIMARY)
        self.screen.blit(c_title, (rect_classic.x + 14, rect_classic.y + 16))
        c_badge = self.font_micro.render("STANDARD FIDE RULES", True, ACCENT_COLOR)
        self.screen.blit(c_badge, (rect_classic.x + 14, rect_classic.y + 40))

        c_lines = [
            "• Pure traditional chess",
            "• 2-Player turns",
            "• Castling & En Passant",
            "• Full promotion selector",
            "• Checkmate & Draw rules",
        ]
        for idx, line in enumerate(c_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_classic.x + 14, rect_classic.y + 64 + idx * 20))

        btn_c_rect = pygame.Rect(rect_classic.x + 14, rect_classic.bottom - 42, rect_classic.width - 28, 30)
        btn_c_color = ACCENT_HOVER if is_hov_c else ACCENT_COLOR
        pygame.draw.rect(self.screen, btn_c_color, btn_c_rect, border_radius=6)
        btn_c_lbl = self.font_subtitle.render("PLAY CLASSIC [1]", True, (15, 35, 25))
        self.screen.blit(btn_c_lbl, btn_c_lbl.get_rect(center=btn_c_rect.center))

        # 2. Chess + UNO Card
        is_hov_u = rect_uno.collidepoint(mouse_pos)
        u_bg = (52, 57, 70) if is_hov_u else (40, 44, 54)
        u_border = GOLD_COLOR if is_hov_u else PANEL_BORDER
        pygame.draw.rect(self.screen, u_bg, rect_uno, border_radius=12)
        pygame.draw.rect(self.screen, u_border, rect_uno, width=2 if is_hov_u else 1, border_radius=12)

        u_title = self.font_header.render("2. Chess + UNO", True, GOLD_COLOR)
        self.screen.blit(u_title, (rect_uno.x + 14, rect_uno.y + 16))
        u_badge = self.font_micro.render("CARD POWER-UPS & FLIPS", True, (240, 160, 60))
        self.screen.blit(u_badge, (rect_uno.x + 14, rect_uno.y + 40))

        u_lines = [
            "• Card shuffle & draw",
            "• 1, 2, or 3 moves / turn",
            "• Reverse: Rotates board",
            "• Skip: Opponent turn lost",
            "• Auto-reshuffling deck",
        ]
        for idx, line in enumerate(u_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_uno.x + 14, rect_uno.y + 64 + idx * 20))

        btn_u_rect = pygame.Rect(rect_uno.x + 14, rect_uno.bottom - 42, rect_uno.width - 28, 30)
        btn_u_color = (255, 215, 90) if is_hov_u else GOLD_COLOR
        pygame.draw.rect(self.screen, btn_u_color, btn_u_rect, border_radius=6)
        btn_u_lbl = self.font_subtitle.render("PLAY UNO [2]", True, (35, 30, 10))
        self.screen.blit(btn_u_lbl, btn_u_lbl.get_rect(center=btn_u_rect.center))

        # 3. Immortal Snail Card
        is_hov_s = rect_snail.collidepoint(mouse_pos)
        s_bg = (52, 57, 70) if is_hov_s else (40, 44, 54)
        s_border = (140, 230, 90) if is_hov_s else PANEL_BORDER
        pygame.draw.rect(self.screen, s_bg, rect_snail, border_radius=12)
        pygame.draw.rect(self.screen, s_border, rect_snail, width=2 if is_hov_s else 1, border_radius=12)

        s_title = self.font_header.render("3. Immortal Snail", True, (140, 230, 90))
        self.screen.blit(s_title, (rect_snail.x + 14, rect_snail.y + 16))
        s_badge = self.font_micro.render("RELENTLESS PURSUIT", True, (160, 240, 100))
        self.screen.blit(s_badge, (rect_snail.x + 14, rect_snail.y + 40))

        s_lines = [
            "• Moves 1 tile every 5 moves",
            "• Relentlessly hunts king",
            "• Crushes routing pieces",
            "• Target caught = game over!",
            "• Immune to capture/block",
        ]
        for idx, line in enumerate(s_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_snail.x + 14, rect_snail.y + 64 + idx * 20))

        btn_s_rect = pygame.Rect(rect_snail.x + 14, rect_snail.bottom - 42, rect_snail.width - 28, 30)
        btn_s_color = (165, 245, 110) if is_hov_s else (135, 220, 85)
        pygame.draw.rect(self.screen, btn_s_color, btn_s_rect, border_radius=6)
        btn_s_lbl = self.font_subtitle.render("PLAY SNAIL [3]", True, (15, 35, 15))
        self.screen.blit(btn_s_lbl, btn_s_lbl.get_rect(center=btn_s_rect.center))

        # 4. Queen Pawn Game Card
        is_hov_qp = rect_queen_pawn.collidepoint(mouse_pos)
        qp_bg = (52, 57, 70) if is_hov_qp else (40, 44, 54)
        qp_border = (245, 105, 180) if is_hov_qp else PANEL_BORDER
        pygame.draw.rect(self.screen, qp_bg, rect_queen_pawn, border_radius=12)
        pygame.draw.rect(self.screen, qp_border, rect_queen_pawn, width=2 if is_hov_qp else 1, border_radius=12)

        qp_title = self.font_header.render("4. Queen Pawn", True, (245, 105, 180))
        self.screen.blit(qp_title, (rect_queen_pawn.x + 14, rect_queen_pawn.y + 16))
        qp_badge = self.font_micro.render("QUEEN & PAWNS CLASH", True, (255, 150, 205))
        self.screen.blit(qp_badge, (rect_queen_pawn.x + 14, rect_queen_pawn.y + 40))

        qp_lines = [
            "• Pawns clash on ranks 4 & 5",
            "• Queens start on d1 & d8",
            "• Capture all pawns to win!",
            "• Queens can be captured",
            "• Tie if only Queens remain",
        ]
        for idx, line in enumerate(qp_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_queen_pawn.x + 14, rect_queen_pawn.y + 64 + idx * 20))

        btn_qp_rect = pygame.Rect(rect_queen_pawn.x + 14, rect_queen_pawn.bottom - 42, rect_queen_pawn.width - 28, 30)
        btn_qp_color = (255, 135, 195) if is_hov_qp else (225, 95, 170)
        pygame.draw.rect(self.screen, btn_qp_color, btn_qp_rect, border_radius=6)
        btn_qp_lbl = self.font_subtitle.render("PLAY Q-PAWN [4]", True, (35, 15, 25))
        self.screen.blit(btn_qp_lbl, btn_qp_lbl.get_rect(center=btn_qp_rect.center))

        # ---------------------------------------------------------------------
        # Pre-Match Match Timer (Time Control) Section
        # ---------------------------------------------------------------------
        pygame.draw.line(self.screen, (58, 64, 76), (screen_w // 2 - 380, 485), (screen_w // 2 + 380, 485), 1)

        timer_title = self.font_header.render("TIME CONTROL (SET MATCH TIMER)", True, GOLD_COLOR)
        self.screen.blit(timer_title, timer_title.get_rect(center=(screen_w // 2, 510)))

        timer_sub = self.font_micro.render("Choose match time limit before starting. Clock begins ticking on first move.", True, TEXT_MUTED)
        self.screen.blit(timer_sub, timer_sub.get_rect(center=(screen_w // 2, 528)))

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
        self.screen.blit(curr_lbl, curr_lbl.get_rect(center=(screen_w // 2 - 18, 609)))

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

        tip_txt = self.font_micro.render("Press [T] during game to cycle timer • Press [Esc] to resume", True, TEXT_MUTED)
        self.screen.blit(tip_txt, tip_txt.get_rect(center=(screen_w // 2, 646)))

        return rect_classic, rect_uno, rect_snail, rect_queen_pawn

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

        # Fullscreen Toggle Button in Header
        fs_label = "Windowed" if is_fullscreen else "Fullscreen"
        self._draw_button(fs_label, self.buttons.fullscreen, mouse_pos)

        is_uno_mode = (game_state.mode.name == "Chess + UNO")
        is_snail_mode = isinstance(game_state.mode, ImmortalSnailMode)
        is_queen_pawn_mode = (game_state.mode.name in ("Queen Pawn", "Queen Pawn Game"))
        if is_snail_mode:
            mode_str = "MODE: IMMORTAL SNAIL"
            mode_color = (140, 230, 90)
        elif is_uno_mode:
            mode_str = "MODE: CHESS + UNO"
            mode_color = GOLD_COLOR
        elif is_queen_pawn_mode:
            mode_str = "MODE: QUEEN PAWN"
            mode_color = (245, 105, 180)
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

        # Turn indicator
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

        # 6. Active Mode Section: UNO Cards or Classic Placeholder
        mod_rect = pygame.Rect(px, 458, pw, 280)
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
            "• [F11] Fullscreen | [F] Flip View",
            "• [R] Restart | [T] Time | [M] Sound",
            fourth_line,
        ]
        for idx, line in enumerate(controls):
            ctrl_txt = self.font_micro.render(line, True, TEXT_SECONDARY)
            self.screen.blit(ctrl_txt, (px, 776 + idx * 18))

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
