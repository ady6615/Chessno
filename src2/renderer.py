# renderer.py
"""
Rendering system for Chessno.

Handles all Pygame drawing routines:
- Chessboard drawing with configurable origin and size
- Highlighting: selected piece, legal destinations (move vs capture), last move, king in check
- Centered piece rendering derived strictly from authoritative GameState
- Drag-and-drop piece rendering
- In-game Pawn Promotion dialog overlay
- Right-side information panel with theme switcher, controls, and mod card slot
"""

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


class UIButtons:
    """Stores bounding rectangles for clickable panel buttons."""
    def __init__(self, panel_x: int, panel_width: int):
        self.panel_x = panel_x
        self.panel_width = panel_width
        
        # Theme switching buttons
        self.prev_theme = pygame.Rect(panel_x, 340, 65, 36)
        self.next_theme = pygame.Rect(panel_x + panel_width - 65, 340, 65, 36)
        
        # Action buttons
        self.new_game = pygame.Rect(panel_x, 400, panel_width, 38)
        self.flip_board = pygame.Rect(panel_x, 448, (panel_width - 10) // 2, 36)
        self.sound_toggle = pygame.Rect(panel_x + (panel_width - 10) // 2 + 10, 448, (panel_width - 10) // 2, 36)


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

        self.buttons = UIButtons(panel_x, panel_width)

        # Pre-create highlight overlays for high performance
        self._surf_selected = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_selected.fill((255, 220, 0, 85))

        self._surf_last_move = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_last_move.fill((65, 205, 120, 65))

        self._surf_check = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        self._surf_check.fill((235, 60, 60, 110))

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
                # Draw sharp inner red border
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

            center = rect.center
            if target_piece is not None or is_ep:
                # Capture target: draw corner capture markers / capture ring
                ring_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                ring_center = (self.square_size // 2, self.square_size // 2)
                pygame.draw.circle(ring_surface, (235, 75, 75, 160), ring_center, self.square_size // 2 - 4, width=5)
                self.screen.blit(ring_surface, rect.topleft)
            else:
                # Empty square: subtle elegant dot
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

        # Modal layout: 4 vertical buttons or 2x2 grid centered near destination
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
                # Scale piece to fit comfortably inside button
                scaled = pygame.transform.smoothscale(img, (38, 38))
                img_rect = scaled.get_rect(center=(btn_rect.centerx, btn_rect.centery))
                self.screen.blit(scaled, img_rect)

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
        self.screen.blit(title, (px, 35))

        mode_badge = self.font_subtitle.render("MODE: CLASSIC CHESS", True, ACCENT_COLOR)
        self.screen.blit(mode_badge, (px, 70))

        pygame.draw.line(self.screen, PANEL_BORDER, (px, 92), (px + pw, 92), 1)

        # 2. Turn & Status Card
        card_rect = pygame.Rect(px, 105, pw, 95)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, card_rect, width=1, border_radius=8)

        # Turn indicator
        turn_str = "WHITE TO MOVE" if game_state.turn == chess.WHITE else "BLACK TO MOVE"
        turn_color = TEXT_PRIMARY if game_state.turn == chess.WHITE else (210, 215, 225)
        indicator_bg = (240, 240, 240) if game_state.turn == chess.WHITE else (30, 32, 40)
        indicator_border = (200, 200, 200) if game_state.turn == chess.WHITE else (100, 105, 120)

        # Mini piece indicator circle
        pygame.draw.circle(self.screen, indicator_bg, (px + 22, 130), 10)
        pygame.draw.circle(self.screen, indicator_border, (px + 22, 130), 10, width=2)

        turn_lbl = self.font_header.render(turn_str, True, turn_color)
        self.screen.blit(turn_lbl, (px + 40, 120))

        # Status badge
        status_text = game_state.status_summary()
        if game_state.is_game_over():
            badge_color = GOLD_COLOR
            badge_bg = (70, 60, 25)
        elif game_state.is_in_check():
            badge_color = CHECK_COLOR
            badge_bg = (70, 30, 30)
        else:
            badge_color = ACCENT_COLOR
            badge_bg = (25, 55, 40)

        status_rect = pygame.Rect(px + 12, 155, pw - 24, 30)
        pygame.draw.rect(self.screen, badge_bg, status_rect, border_radius=6)
        pygame.draw.rect(self.screen, badge_color, status_rect, width=1, border_radius=6)

        status_lbl = self.font_small.render(status_text, True, badge_color)
        lbl_rect = status_lbl.get_rect(center=status_rect.center)
        self.screen.blit(status_lbl, lbl_rect)

        # 3. Game Stats / History Card
        stats_rect = pygame.Rect(px, 212, pw, 72)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, stats_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, stats_rect, width=1, border_radius=8)

        move_num = game_state.fullmove_number
        last_san = game_state.move_history[-1].san if game_state.move_history else "-"
        
        stat1 = self.font_small.render(f"Move: {move_num}", True, TEXT_SECONDARY)
        stat2 = self.font_small.render(f"Last Move: {last_san}", True, ACCENT_COLOR)
        self.screen.blit(stat1, (px + 14, 222))
        self.screen.blit(stat2, (px + 14, 248))

        # 4. Theme Selection Section
        theme_lbl = self.font_subtitle.render("PIECE & BOARD THEME", True, TEXT_MUTED)
        self.screen.blit(theme_lbl, (px, 298))

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

        # 6. Future Mod Slot Card (UNO Cards / Immortal Snail)
        mod_rect = pygame.Rect(px, 502, pw, 230)
        pygame.draw.rect(self.screen, PANEL_CARD_BG, mod_rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, mod_rect, width=1, border_radius=8)

        mod_title = self.font_subtitle.render("MODS & UNO CARDS", True, GOLD_COLOR)
        self.screen.blit(mod_title, (px + 14, 514))

        mod_desc = [
            "Reserved deck slot for",
            "upcoming game modes:",
            "- Chess + UNO Cards",
            "- Immortal Snail Hazard",
            "- Online Multiplayer",
        ]
        for idx, line in enumerate(mod_desc):
            txt = self.font_small.render(line, True, TEXT_SECONDARY)
            self.screen.blit(txt, (px + 14, 542 + idx * 22))

        # Stylized card slot placeholder outlines
        card_w, card_h = 56, 76
        for c in range(3):
            cx = px + 18 + c * (card_w + 12)
            cy = 642
            slot = pygame.Rect(cx, cy, card_w, card_h)
            pygame.draw.rect(self.screen, (34, 38, 46), slot, border_radius=6)
            pygame.draw.rect(self.screen, (68, 74, 88), slot, width=1, border_radius=6)
            slot_lbl = self.font_micro.render("CARD", True, TEXT_MUTED)
            sl_rect = slot_lbl.get_rect(center=slot.center)
            self.screen.blit(slot_lbl, sl_rect)

        # 7. Quick Controls Footer
        pygame.draw.line(self.screen, PANEL_BORDER, (px, 750), (px + pw, 750), 1)
        help_title = self.font_subtitle.render("CONTROLS", True, TEXT_MUTED)
        self.screen.blit(help_title, (px, 762))

        controls = [
            "• Click piece + click target square",
            "• Or drag-and-drop piece",
            "• [R] Restart Game | [F] Flip View",
            "• [Left / Right] Switch Theme",
        ]
        for idx, line in enumerate(controls):
            ctrl_txt = self.font_micro.render(line, True, TEXT_SECONDARY)
            self.screen.blit(ctrl_txt, (px, 786 + idx * 18))

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
