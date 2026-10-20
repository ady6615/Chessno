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

# Theme and UI Color Palette
BG_COLOR = (26, 28, 34)
PANEL_BG = (35, 38, 46)
PANEL_CARD_BG = (44, 48, 58)
PANEL_BORDER = (58, 64, 76)
TEXT_PRIMARY = (245, 246, 250)
TEXT_SECONDARY = (165, 172, 185)
TEXT_MUTED = (115, 122, 135)
ACCENT_COLOR = (86, 182, 139)       # Mint green
ACCENT_HOVER = (106, 202, 159)
CHECK_COLOR = (235, 87, 87)         # Crimson alert
CHECK_HOVER = (255, 107, 107)
GOLD_COLOR = (242, 201, 76)         # Highlight gold
BTN_COLOR = (54, 59, 72)
BTN_HOVER = (72, 79, 96)
BTN_BORDER = (82, 90, 108)

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
        
        # Mode selector button in header
        self.mode_select = pygame.Rect(panel_x + panel_width - 100, 64, 100, 26)

        # Theme switching buttons
        self.prev_theme = pygame.Rect(panel_x, 340, 65, 36)
        self.next_theme = pygame.Rect(panel_x + panel_width - 65, 340, 65, 36)
        
        # Action buttons
        self.new_game = pygame.Rect(panel_x, 400, panel_width, 38)
        self.flip_board = pygame.Rect(panel_x, 448, (panel_width - 10) // 2, 36)
        self.sound_toggle = pygame.Rect(panel_x + (panel_width - 10) // 2 + 10, 448, (panel_width - 10) // 2, 36)

        # UNO Interactive Buttons
        self.draw_card = pygame.Rect(panel_x + 14, 664, panel_width - 28, 40)
        self.deck_card = pygame.Rect(panel_x + (panel_width - 105) // 2, 506, 105, 145)

        # Immortal Snail Target Selection Buttons
        btn_w = (panel_width - 34) // 2
        self.target_white = pygame.Rect(panel_x + 14, 542, btn_w, 28)
        self.target_black = pygame.Rect(panel_x + 14 + btn_w + 6, 542, btn_w, 28)


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

        # Initialize typography
        self.font_title = pygame.font.SysFont("arial", 26, bold=True)
        self.font_subtitle = pygame.font.SysFont("arial", 13, bold=True)
        self.font_header = pygame.font.SysFont("arial", 17, bold=True)
        self.font_normal = pygame.font.SysFont("arial", 15)
        self.font_small = pygame.font.SysFont("arial", 13)
        self.font_micro = pygame.font.SysFont("arial", 11)
        self.font_card_large = pygame.font.SysFont("arial", 46, bold=True)
        self.font_card_med = pygame.font.SysFont("arial", 22, bold=True)
        self.font_card_corner = pygame.font.SysFont("arial", 14, bold=True)

        self.buttons = UIButtons(panel_x, panel_width)

        # Pre-create highlight overlays for high performance
        self._surf_selected = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_selected.fill((255, 220, 0, 85))

        self._surf_last_move = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_last_move.fill((65, 205, 120, 65))

        self._surf_check = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_check.fill((235, 60, 60, 110))
        self._snail_sprite_cache: Dict[int, pygame.Surface] = {}

    # -------------------------------------------------------------------------
    # Board & Square Highlights
    # -------------------------------------------------------------------------

    def draw_board(self, board_image: pygame.Surface) -> None:
        """Render the 8x8 chessboard background sprite."""
        self.screen.blit(board_image, (self.board_x, self.board_y))

    def draw_highlights(
        self,
        game_state: GameState,
        selected_square: Optional[chess.Square],
        legal_destinations: List[chess.Square],
        flipped: bool = False,
    ) -> None:
        """
        Draw all contextual square highlights:
        - Last move from/to squares
        - King in check alert
        - Selected piece square
        - Legal move indicators (dots for empty squares, target rings for captures)
        """
        # 1. Last move highlight
        if game_state.last_move:
            for sq in game_state.last_move:
                rect = square_to_rect(
                    sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                self.screen.blit(self._surf_last_move, rect.topleft)

        # 2. King in check highlight
        if game_state.is_in_check():
            king_sq = game_state.king_square()
            if king_sq is not None:
                rect = square_to_rect(
                    king_sq, flipped=flipped, board_x=self.board_x, board_y=self.board_y, square_size=self.square_size
                )
                self.screen.blit(self._surf_check, rect.topleft)
                pygame.draw.rect(self.screen, (240, 50, 50), rect, width=3)

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
                ring_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                ring_center = (self.square_size // 2, self.square_size // 2)
                pygame.draw.circle(ring_surface, (235, 75, 75, 160), ring_center, self.square_size // 2 - 4, width=5)
                self.screen.blit(ring_surface, rect.topleft)
            else:
                dot_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                dot_center = (self.square_size // 2, self.square_size // 2)
                pygame.draw.circle(dot_surface, (80, 220, 140, 175), dot_center, 12)
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
    # Game Mode Selection Start Menu / Modal
    # -------------------------------------------------------------------------

    def get_mode_selector_rects(self) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Return clickable rectangles for (Classic_Chess_card, Chess_UNO_card, Immortal_Snail_card)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        card_w, card_h = 264, 276
        gap = 20
        total_w = card_w * 3 + gap * 2
        start_x = (screen_w - total_w) // 2
        card_y = (screen_h - card_h) // 2 + 25

        rect_classic = pygame.Rect(start_x, card_y, card_w, card_h)
        rect_uno = pygame.Rect(start_x + card_w + gap, card_y, card_w, card_h)
        rect_snail = pygame.Rect(start_x + (card_w + gap) * 2, card_y, card_w, card_h)
        return rect_classic, rect_uno, rect_snail

    def draw_mode_selector_modal(self, mouse_pos: Tuple[int, int]) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """
        Draw a modal start menu allowing the player to select the game mode.
        Returns the three card Rects for event collision checking.
        """
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((12, 14, 18, 225))
        self.screen.blit(overlay, (0, 0))

        title_y = screen_h // 2 - 200
        title_surf = self.font_title.render("SELECT GAME MODE", True, TEXT_PRIMARY)
        t_rect = title_surf.get_rect(center=(screen_w // 2, title_y))
        self.screen.blit(title_surf, t_rect)

        sub_surf = self.font_normal.render("Choose your Chessno game mode or press [1], [2], [3]", True, TEXT_SECONDARY)
        s_rect = sub_surf.get_rect(center=(screen_w // 2, title_y + 36))
        self.screen.blit(sub_surf, s_rect)

        rect_classic, rect_uno, rect_snail = self.get_mode_selector_rects()

        # 1. Classic Chess Card
        is_hov_c = rect_classic.collidepoint(mouse_pos)
        c_bg = (52, 57, 70) if is_hov_c else (40, 44, 54)
        c_border = ACCENT_COLOR if is_hov_c else PANEL_BORDER
        pygame.draw.rect(self.screen, c_bg, rect_classic, border_radius=12)
        pygame.draw.rect(self.screen, c_border, rect_classic, width=2 if is_hov_c else 1, border_radius=12)

        c_title = self.font_header.render("1. Classic Chess", True, TEXT_PRIMARY)
        self.screen.blit(c_title, (rect_classic.x + 18, rect_classic.y + 20))
        c_badge = self.font_micro.render("STANDARD FIDE RULES", True, ACCENT_COLOR)
        self.screen.blit(c_badge, (rect_classic.x + 18, rect_classic.y + 48))

        c_lines = [
            "• Pure traditional chess",
            "• 2-Player alternating turns",
            "• Castling & En Passant",
            "• Full promotion selector",
            "• Checkmate & Draw rules",
        ]
        for idx, line in enumerate(c_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_classic.x + 18, rect_classic.y + 78 + idx * 21))

        btn_c_rect = pygame.Rect(rect_classic.x + 18, rect_classic.bottom - 44, rect_classic.width - 36, 30)
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
        self.screen.blit(u_title, (rect_uno.x + 18, rect_uno.y + 20))
        u_badge = self.font_micro.render("CARD POWER-UPS & FLIPS", True, (240, 160, 60))
        self.screen.blit(u_badge, (rect_uno.x + 18, rect_uno.y + 48))

        u_lines = [
            "• Animated card shuffle & draw",
            "• 1, 2, or 3 moves per turn",
            "• Reverse: Rotates board 180°",
            "• Skip: Opponent loses turn",
            "• Auto-reshuffling deck",
        ]
        for idx, line in enumerate(u_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_uno.x + 18, rect_uno.y + 78 + idx * 21))

        btn_u_rect = pygame.Rect(rect_uno.x + 18, rect_uno.bottom - 44, rect_uno.width - 36, 30)
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
        self.screen.blit(s_title, (rect_snail.x + 18, rect_snail.y + 20))
        s_badge = self.font_micro.render("RELENTLESS PURSUIT HAZARD", True, (160, 240, 100))
        self.screen.blit(s_badge, (rect_snail.x + 18, rect_snail.y + 48))

        s_lines = [
            "• Moves 1 tile every 3 moves",
            "• Relentlessly hunts target king",
            "• Crushes any piece in its route",
            "• Target king caught = game over!",
            "• Immune to capture or blocks",
        ]
        for idx, line in enumerate(s_lines):
            t = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(t, (rect_snail.x + 18, rect_snail.y + 78 + idx * 21))

        btn_s_rect = pygame.Rect(rect_snail.x + 18, rect_snail.bottom - 44, rect_snail.width - 36, 30)
        btn_s_color = (165, 245, 110) if is_hov_s else (135, 220, 85)
        pygame.draw.rect(self.screen, btn_s_color, btn_s_rect, border_radius=6)
        btn_s_lbl = self.font_subtitle.render("PLAY SNAIL [3]", True, (15, 35, 15))
        self.screen.blit(btn_s_lbl, btn_s_lbl.get_rect(center=btn_s_rect.center))

        return rect_classic, rect_uno, rect_snail

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
    ) -> None:
        """Render the complete right-hand info panel."""
        panel_rect = pygame.Rect(self.panel_x - 15, 0, self.screen.get_width() - self.panel_x + 15, self.screen.get_height())
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (self.panel_x - 15, 0), (self.panel_x - 15, self.screen.get_height()), 2)

        px = self.panel_x
        pw = self.panel_width

        # 1. Header & Brand
        title = self.font_title.render("CHESSNO", True, TEXT_PRIMARY)
        self.screen.blit(title, (px, 32))

        is_uno_mode = (game_state.mode.name == "Chess + UNO")
        is_snail_mode = isinstance(game_state.mode, ImmortalSnailMode)
        if is_snail_mode:
            mode_str = "MODE: IMMORTAL SNAIL"
            mode_color = (140, 230, 90)
        elif is_uno_mode:
            mode_str = "MODE: CHESS + UNO"
            mode_color = GOLD_COLOR
        else:
            mode_str = "MODE: CLASSIC"
            mode_color = ACCENT_COLOR

        mode_badge = self.font_subtitle.render(mode_str, True, mode_color)
        self.screen.blit(mode_badge, (px, 70))

        # Mode switch button
        self._draw_button("Mode", self.buttons.mode_select, mouse_pos)

        pygame.draw.line(self.screen, PANEL_BORDER, (px, 94), (px + pw, 94), 1)

        # 2. Turn & Status Card
        card_rect = pygame.Rect(px, 102, pw, 98)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, card_rect, width=1, border_radius=8)

        # Turn indicator
        turn_str = "WHITE TO MOVE" if game_state.turn == chess.WHITE else "BLACK TO MOVE"
        turn_color = TEXT_PRIMARY if game_state.turn == chess.WHITE else (210, 215, 225)
        indicator_bg = (240, 240, 240) if game_state.turn == chess.WHITE else (30, 32, 40)
        indicator_border = (200, 200, 200) if game_state.turn == chess.WHITE else (100, 105, 120)

        pygame.draw.circle(self.screen, indicator_bg, (px + 22, 126), 10)
        pygame.draw.circle(self.screen, indicator_border, (px + 22, 126), 10, width=2)

        turn_lbl = self.font_header.render(turn_str, True, turn_color)
        self.screen.blit(turn_lbl, (px + 40, 116))

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

        status_rect = pygame.Rect(px + 12, 154, pw - 24, 30)
        pygame.draw.rect(self.screen, badge_bg, status_rect, border_radius=6)
        pygame.draw.rect(self.screen, badge_color, status_rect, width=1, border_radius=6)

        status_lbl = self.font_small.render(status_text, True, badge_color)
        lbl_rect = status_lbl.get_rect(center=status_rect.center)
        self.screen.blit(status_lbl, lbl_rect)

        # 3. Game Stats / History Card
        stats_rect = pygame.Rect(px, 208, pw, 72)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, stats_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, stats_rect, width=1, border_radius=8)

        move_num = game_state.fullmove_number
        last_san = game_state.move_history[-1].san if game_state.move_history else "-"
        
        stat1 = self.font_small.render(f"Move: {move_num}", True, TEXT_SECONDARY)
        stat2 = self.font_small.render(f"Last Move: {last_san}", True, ACCENT_COLOR)
        self.screen.blit(stat1, (px + 14, 218))
        self.screen.blit(stat2, (px + 14, 244))

        # 4. Theme Selection Section
        theme_lbl = self.font_subtitle.render("PIECE & BOARD THEME", True, TEXT_MUTED)
        self.screen.blit(theme_lbl, (px, 292))

        pack_info = f"{active_pack_name} ({active_pack_index + 1}/{total_packs})"
        pack_text = self.font_small.render(pack_info, True, TEXT_PRIMARY)
        pack_rect = pack_text.get_rect(centerx=px + pw // 2, centery=358)
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
        mod_rect = pygame.Rect(px, 498, pw, 246)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, mod_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, mod_rect, width=1, border_radius=8)

        if is_uno_mode and hasattr(game_state.mode, "phase"):
            mode = game_state.mode
            deck = mode.deck
            phase_val = mode.phase.value

            card_cx = px + pw // 2
            card_cy = 574

            # STATE 1: Awaiting Draw (Button + Deck)
            if phase_val == "Awaiting Draw":
                # Render deck of cards
                self.draw_uno_card_back(card_cx, card_cy, width=105, height=140)

                # "Draw Card" button
                self._draw_button("Draw Card", self.buttons.draw_card, mouse_pos, accent=True)

                # Subtle hint
                hint_str = "Click button or press [Space]"
                h_surf = self.font_micro.render(hint_str, True, (240, 205, 80))
                self.screen.blit(h_surf, h_surf.get_rect(center=(px + pw // 2, 718)))

            # STATE 2: Shuffling animation in progress
            elif phase_val == "Shuffling":
                self.draw_shuffling_animation(card_cx, card_cy, mode.shuffle_progress, width=105, height=140)

                dots = "." * (1 + (int(pygame.time.get_ticks() / 150) % 3))
                shuff_str = f"Shuffling Deck{dots}"
                s_surf = self.font_subtitle.render(shuff_str, True, GOLD_COLOR)
                self.screen.blit(s_surf, s_surf.get_rect(center=(px + pw // 2, 672)))

                deck_str = f"Deck: {deck.draw_pile_count} left"
                d_surf = self.font_micro.render(deck_str, True, TEXT_SECONDARY)
                self.screen.blit(d_surf, d_surf.get_rect(center=(px + pw // 2, 700)))

            # STATE 3: Card is revealed and active
            else:
                card = mode.current_card
                if card is not None:
                    self.draw_uno_card_graphic(card, card_cx, card_cy, width=105, height=140)

                    # Move indicator
                    rem = mode.moves_remaining
                    tot = mode.moves_allowed
                    move_info_str = f"Moves: {tot - rem + 1} of {tot}"
                    m_surf = self.font_subtitle.render(move_info_str, True, GOLD_COLOR)
                    self.screen.blit(m_surf, m_surf.get_rect(center=(px + pw // 2, 668)))

                    # Deck counts
                    deck_str = f"Deck: {deck.draw_pile_count} left | Discard: {deck.discard_pile_count}"
                    d_surf = self.font_micro.render(deck_str, True, TEXT_SECONDARY)
                    self.screen.blit(d_surf, d_surf.get_rect(center=(px + pw // 2, 692)))

                    # Alert or card description
                    if mode.skip_alert_message:
                        alert_surf = self.font_micro.render(mode.skip_alert_message, True, CHECK_COLOR)
                        self.screen.blit(alert_surf, alert_surf.get_rect(center=(px + pw // 2, 716)))
                    elif mode.pending_skips > 0:
                        skip_surf = self.font_micro.render(f"Pending Skips: {mode.pending_skips}", True, (240, 160, 50))
                        self.screen.blit(skip_surf, skip_surf.get_rect(center=(px + pw // 2, 716)))
                    else:
                        desc_surf = self.font_micro.render(card.description, True, TEXT_MUTED)
                        self.screen.blit(desc_surf, desc_surf.get_rect(center=(px + pw // 2, 716)))

        elif is_snail_mode:
            mode = game_state.mode
            mod_title = self.font_subtitle.render("DUAL IMMORTAL SNAILS", True, (140, 230, 90))
            self.screen.blit(mod_title, (px + 14, 506))

            # Move Countdown (Every 5 moves)
            rem_moves = mode.moves_until_next_step
            step_lbl = self.font_small.render("Next step:", True, TEXT_PRIMARY)
            self.screen.blit(step_lbl, (px + 14, 528))

            pip_w = 22
            pip_h = 14
            pip_start_x = px + 88
            for p in range(5):
                pip_rect = pygame.Rect(pip_start_x + p * (pip_w + 4), 530, pip_w, pip_h)
                filled = (p < (5 - rem_moves))
                if filled:
                    pygame.draw.rect(self.screen, (140, 220, 80), pip_rect, border_radius=3)
                else:
                    pygame.draw.rect(self.screen, (50, 56, 68), pip_rect, border_radius=3)
                    pygame.draw.rect(self.screen, (75, 82, 98), pip_rect, width=1, border_radius=3)

            count_desc = f"{rem_moves} legal move{'s' if rem_moves > 1 else ''} until step (every 5)"
            desc_surf = self.font_micro.render(count_desc, True, (140, 220, 80) if rem_moves == 1 else TEXT_MUTED)
            self.screen.blit(desc_surf, (px + 14, 548))

            # White Snail Info Card
            w_snail = mode.white_snail
            w_dist = w_snail.distance_to_target(game_state)
            w_dist_str = f"{w_dist} tiles" if w_dist is not None else "N/A"
            w_card_rect = pygame.Rect(px + 10, 568, pw - 20, 54)
            pygame.draw.rect(self.screen, (34, 46, 42), w_card_rect, border_radius=6)
            pygame.draw.rect(self.screen, (90, 215, 185), w_card_rect, width=1, border_radius=6)

            w_title = self.font_micro.render(f"WHITE SNAIL [{w_snail.location_name}]", True, (140, 255, 230))
            w_sub1 = self.font_micro.render(f"Hunting Black King ({w_dist_str} away)", True, TEXT_PRIMARY)
            w_sub2 = self.font_micro.render(f"Crushed: {len(w_snail.crushed_pieces)} Black pieces", True, TEXT_MUTED)
            self.screen.blit(w_title, (px + 16, 572))
            self.screen.blit(w_sub1, (px + 16, 588))
            self.screen.blit(w_sub2, (px + 16, 604))

            # Black Snail Info Card
            b_snail = mode.black_snail
            b_dist = b_snail.distance_to_target(game_state)
            b_dist_str = f"{b_dist} tiles" if b_dist is not None else "N/A"
            b_card_rect = pygame.Rect(px + 10, 626, pw - 20, 54)
            pygame.draw.rect(self.screen, (46, 34, 38), b_card_rect, border_radius=6)
            pygame.draw.rect(self.screen, (240, 95, 95), b_card_rect, width=1, border_radius=6)

            b_title = self.font_micro.render(f"BLACK SNAIL [{b_snail.location_name}]", True, (255, 140, 140))
            b_sub1 = self.font_micro.render(f"Hunting White King ({b_dist_str} away)", True, TEXT_PRIMARY)
            b_sub2 = self.font_micro.render(f"Crushed: {len(b_snail.crushed_pieces)} White pieces", True, TEXT_MUTED)
            self.screen.blit(b_title, (px + 16, 630))
            self.screen.blit(b_sub1, (px + 16, 646))
            self.screen.blit(b_sub2, (px + 16, 662))

            # Friendly Safety Notice
            safe_lbl = self.font_micro.render("Friendly pieces safe: Snails detour around own team", True, (130, 205, 140))
            self.screen.blit(safe_lbl, safe_lbl.get_rect(center=(px + pw // 2, 692)))

            # Alert or Victory
            if mode.target_caught:
                win_rect = pygame.Rect(px + 10, 706, pw - 20, 32)
                pygame.draw.rect(self.screen, (70, 25, 25), win_rect, border_radius=6)
                pygame.draw.rect(self.screen, CHECK_COLOR, win_rect, width=2, border_radius=6)
                vic_msg = "WHITE SNAIL CAUGHT BLACK KING!" if w_snail.target_caught else "BLACK SNAIL CAUGHT WHITE KING!"
                w_title = self.font_micro.render(vic_msg, True, CHECK_COLOR)
                self.screen.blit(w_title, w_title.get_rect(center=win_rect.center))
            else:
                steps_txt = f"Total steps taken: {mode.steps_taken}"
                s_surf = self.font_micro.render(steps_txt, True, TEXT_MUTED)
                self.screen.blit(s_surf, s_surf.get_rect(center=(px + pw // 2, 715)))

        else:
            # Classic mode placeholder
            mod_title = self.font_subtitle.render("MODS & UNO CARDS", True, TEXT_MUTED)
            self.screen.blit(mod_title, (px + 14, 510))

            mod_desc = [
                "Currently in Classic Chess.",
                "Click 'Mode' at the top to",
                "switch to UNO or Snail mode!",
                "",
                "Available Modes:",
                "- Chess + UNO Powerups",
                "- Immortal Snail Hazard",
            ]
            for idx, line in enumerate(mod_desc):
                txt = self.font_small.render(line, True, TEXT_SECONDARY)
                self.screen.blit(txt, (px + 14, 538 + idx * 21))

            card_w, card_h = 56, 76
            for c in range(3):
                cx = px + 18 + c * (card_w + 12)
                cy = 650
                slot = pygame.Rect(cx, cy, card_w, card_h)
                pygame.draw.rect(self.screen, (34, 38, 46), slot, border_radius=6)
                pygame.draw.rect(self.screen, (68, 74, 88), slot, width=1, border_radius=6)
                slot_lbl = self.font_micro.render("CARD", True, TEXT_MUTED)
                sl_rect = slot_lbl.get_rect(center=slot.center)
                self.screen.blit(slot_lbl, sl_rect)

        # 7. Quick Controls Footer
        pygame.draw.line(self.screen, PANEL_BORDER, (px, 755), (px + pw, 755), 1)
        help_title = self.font_subtitle.render("CONTROLS", True, TEXT_MUTED)
        self.screen.blit(help_title, (px, 765))

        controls = [
            "• Click piece + click target square",
            "• Or drag-and-drop piece",
            "• [R] Restart Game | [F] Flip View",
            "• [Space] Draw Card (UNO mode)",
        ]
        for idx, line in enumerate(controls):
            ctrl_txt = self.font_micro.render(line, True, TEXT_SECONDARY)
            self.screen.blit(ctrl_txt, (px, 788 + idx * 18))

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
            border_color = (130, 220, 180)
            text_color = (15, 35, 25)
        else:
            color = BTN_HOVER if hovered else BTN_COLOR
            border_color = (110, 120, 140) if hovered else BTN_BORDER
            text_color = TEXT_PRIMARY

        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, border_color, rect, width=1, border_radius=6)

        label = self.font_small.render(text, True, text_color)
        label_rect = label.get_rect(center=rect.center)
        self.screen.blit(label, label_rect)
