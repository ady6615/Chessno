# main.py
"""
Chessno - Main Application Entry Point

Features:
- Complete standard FIDE chess rules via python-chess (castling, en passant, promotion, checks, checkmate, draws)
- Seamless dual interaction: click-to-move AND drag-and-drop
- In-game interactive pawn promotion selector
- Real-time square highlighting for legal moves, captures, last move, and king in check
- Dynamic asset pack (theme) switching
- Audio system with custom WAV file support and procedural fallback
- Board flip capability (view from White or Black perspective)
- Extensible architecture ready for Chess + UNO, Immortal Snail, and Multiplayer
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, List
import pygame
import chess

# Ensure local imports resolve when executed directly or via root
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import Assets
import ChessMatrix
from coordinates import (
    BOARD_X,
    BOARD_Y,
    SQUARE_SIZE,
    BOARD_SIZE,
    pixel_to_square,
    piece_to_code,
)
from game_engine import GameState, ClassicChessMode
from renderer import ChessRenderer, BG_COLOR

# Window dimensions
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900
PANEL_X = 900
PANEL_WIDTH = 270


def play_move_sound(result) -> None:
    """Trigger the appropriate sound effect based on the move's outcome."""
    if result.is_checkmate:
        Assets.play_sound("game_over")
    elif result.is_check:
        Assets.play_sound("check")
    elif result.is_promotion:
        Assets.play_sound("promotion")
    elif result.is_castling:
        Assets.play_sound("castle")
    elif result.is_capture:
        Assets.play_sound("capture")
    else:
        Assets.play_sound("move")


def main() -> None:
    # 1. Initialize Pygame
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Chessno - Complete Chess")
    clock = pygame.time.Clock()
    FPS = 60

    # 2. Load Assets & Themes
    board_image, piece_images = Assets.load_assets()
    available_packs = Assets.get_available_packs()
    if not available_packs:
        raise RuntimeError("No asset packs found. Ensure 'assets' directory contains at least one theme.")

    active_pack_index = available_packs.index(Assets.get_active_asset_pack())

    # 3. Initialize Game Engine & Authoritative State
    game_state = GameState(mode=ClassicChessMode())
    ChessMatrix.set_active_game_state(game_state)

    # 4. Initialize Renderer
    renderer = ChessRenderer(
        screen=screen,
        board_x=BOARD_X,
        board_y=BOARD_Y,
        square_size=SQUARE_SIZE,
        panel_x=PANEL_X,
        panel_width=PANEL_WIDTH,
    )

    # 5. Interaction State
    selected_square: Optional[chess.Square] = None
    legal_destinations: List[chess.Square] = []
    dragging: bool = False
    drag_start_square: Optional[chess.Square] = None
    flipped: bool = False  # False: White at bottom; True: Black at bottom
    pending_promotion: Optional[Tuple[chess.Square, chess.Square]] = None

    Assets.play_sound("game_start")

    def change_theme(direction: int) -> None:
        nonlocal active_pack_index, board_image, piece_images
        new_index = (active_pack_index + direction) % len(available_packs)
        pack_name = available_packs[new_index]
        try:
            new_board, new_pieces = Assets.switch_asset_pack(pack_name)
            board_image = new_board
            piece_images = new_pieces
            active_pack_index = new_index
        except Exception as err:
            print(f"Error switching theme to '{pack_name}': {err}")

    # 6. Main Game Loop
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ---------------------------------------------------------
            # MOUSE BUTTON DOWN
            # ---------------------------------------------------------
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Handle promotion modal interaction
                if pending_promotion is not None:
                    from_sq, to_sq = pending_promotion
                    options = renderer.get_promotion_options(game_state.turn, to_sq, flipped=flipped)
                    option_clicked = False
                    for ptype, btn_rect, _ in options:
                        if btn_rect.collidepoint(event.pos):
                            # Commit move with chosen promotion piece
                            result = game_state.make_move(from_sq, to_sq, promotion=ptype)
                            if result.success:
                                play_move_sound(result)
                            pending_promotion = None
                            selected_square = None
                            legal_destinations = []
                            option_clicked = True
                            break

                    if not option_clicked:
                        # Clicked outside modal: cancel promotion and selection
                        pending_promotion = None
                        selected_square = None
                        legal_destinations = []
                    continue

                # Check UI Button Clicks
                if renderer.buttons.prev_theme.collidepoint(event.pos):
                    change_theme(-1)
                    continue

                if renderer.buttons.next_theme.collidepoint(event.pos):
                    change_theme(1)
                    continue

                if renderer.buttons.new_game.collidepoint(event.pos):
                    game_state.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    Assets.play_sound("game_start")
                    continue

                if renderer.buttons.flip_board.collidepoint(event.pos):
                    flipped = not flipped
                    continue

                if renderer.buttons.sound_toggle.collidepoint(event.pos):
                    Assets.toggle_sound()
                    continue

                # Board square click
                clicked_sq = pixel_to_square(
                    event.pos,
                    flipped=flipped,
                    board_x=BOARD_X,
                    board_y=BOARD_Y,
                    square_size=SQUARE_SIZE,
                )

                if clicked_sq is not None:
                    # Case 1: Already had a piece selected
                    if selected_square is not None:
                        # Click-to-move destination?
                        if clicked_sq in legal_destinations:
                            if game_state.needs_promotion(selected_square, clicked_sq):
                                pending_promotion = (selected_square, clicked_sq)
                            else:
                                result = game_state.make_move(selected_square, clicked_sq)
                                if result.success:
                                    play_move_sound(result)
                                selected_square = None
                                legal_destinations = []
                        else:
                            # Clicked another piece of the same player?
                            piece = game_state.get_piece_at(clicked_sq)
                            if piece is not None and piece.color == game_state.turn:
                                selected_square = clicked_sq
                                legal_destinations = game_state.get_legal_destinations(clicked_sq)
                                dragging = True
                                drag_start_square = clicked_sq
                            else:
                                # Deselect
                                selected_square = None
                                legal_destinations = []

                    # Case 2: No piece currently selected
                    else:
                        piece = game_state.get_piece_at(clicked_sq)
                        if piece is not None and piece.color == game_state.turn:
                            selected_square = clicked_sq
                            legal_destinations = game_state.get_legal_destinations(clicked_sq)
                            dragging = True
                            drag_start_square = clicked_sq

            # ---------------------------------------------------------
            # MOUSE BUTTON UP
            # ---------------------------------------------------------
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if dragging and drag_start_square is not None:
                    target_sq = pixel_to_square(
                        event.pos,
                        flipped=flipped,
                        board_x=BOARD_X,
                        board_y=BOARD_Y,
                        square_size=SQUARE_SIZE,
                    )

                    # If released on a different square (drag-and-drop move attempt)
                    if target_sq is not None and target_sq != drag_start_square:
                        if target_sq in legal_destinations:
                            if game_state.needs_promotion(drag_start_square, target_sq):
                                pending_promotion = (drag_start_square, target_sq)
                            else:
                                result = game_state.make_move(drag_start_square, target_sq)
                                if result.success:
                                    play_move_sound(result)
                                selected_square = None
                                legal_destinations = []
                        else:
                            # Illegal drop
                            Assets.play_sound("invalid")
                            selected_square = None
                            legal_destinations = []

                    # If released on same square, preserve selection for click-to-move
                    dragging = False
                    drag_start_square = None

            # ---------------------------------------------------------
            # KEYBOARD SHORTCUTS
            # ---------------------------------------------------------
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game_state.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    Assets.play_sound("game_start")

                elif event.key == pygame.K_f:
                    flipped = not flipped

                elif event.key == pygame.K_RIGHT:
                    change_theme(1)

                elif event.key == pygame.K_LEFT:
                    change_theme(-1)

                elif event.key == pygame.K_m:
                    Assets.toggle_sound()

                elif event.key == pygame.K_ESCAPE:
                    pending_promotion = None
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None

        # -------------------------------------------------------------
        # DRAWING ROUTINE
        # -------------------------------------------------------------
        screen.fill(BG_COLOR)

        # 1. Chessboard background
        renderer.draw_board(board_image)

        # 2. Square highlights (legal moves, last move, king in check, selection)
        renderer.draw_highlights(
            game_state=game_state,
            selected_square=selected_square,
            legal_destinations=legal_destinations,
            flipped=flipped,
        )

        # 3. Chess pieces
        dragging_sq = drag_start_square if dragging else None
        renderer.draw_pieces(
            game_state=game_state,
            piece_images=piece_images,
            dragging_square=dragging_sq,
            flipped=flipped,
        )

        # 4. Floating dragged piece following mouse cursor
        if dragging and selected_square is not None:
            piece = game_state.get_piece_at(selected_square)
            code = piece_to_code(piece)
            if code:
                renderer.draw_dragged_piece(piece_images, code, mouse_pos)

        # 5. Interactive Pawn Promotion Dialog
        if pending_promotion is not None:
            _, promo_sq = pending_promotion
            renderer.draw_promotion_modal(
                color=game_state.turn,
                to_square=promo_sq,
                piece_images=piece_images,
                mouse_pos=mouse_pos,
                flipped=flipped,
            )

        # 6. Right-side Panel
        renderer.draw_panel(
            game_state=game_state,
            active_pack_name=Assets.get_active_asset_pack(),
            active_pack_index=active_pack_index,
            total_packs=len(available_packs),
            mouse_pos=mouse_pos,
            sound_enabled=Assets.is_sound_enabled(),
            flipped=flipped,
        )

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
