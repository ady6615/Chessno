# main.py
"""
Chessno - Main Application Entry Point

Features:
- Selectable game modes: Classic Chess & Chess + UNO
- Start menu and in-game mode switcher
- Complete standard FIDE chess rules via python-chess (castling, en passant, promotion, checks, checkmate, draws)
- Chess + UNO mechanics: 1, 2, 3 multi-move turns, 180° Reverse board flips, and Skips
- Seamless dual interaction: click-to-move AND drag-and-drop
- In-game interactive pawn promotion selector
- Real-time square highlighting for legal moves, captures, last move, and king in check
- Dynamic asset pack (theme) switching
- Audio system with custom WAV file support and procedural fallback
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
from uno_engine import ChessUnoMode, UnoTurnPhase
from snail_engine import ImmortalSnailMode
from timer import ChessTimer
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
    pygame.display.set_caption("Chessno - Chess + UNO")
    clock = pygame.time.Clock()
    FPS = 60

    # 2. Load Assets & Themes
    board_image, piece_images = Assets.load_assets()
    available_packs = Assets.get_available_packs()
    if not available_packs:
        raise RuntimeError("No asset packs found. Ensure 'assets' directory contains at least one theme.")

    active_pack_index = available_packs.index(Assets.get_active_asset_pack())

    # 3. Game State & Mode Management
    # Default initial mode: Classic Chess; Start Menu opened for selection
    current_mode_name = "Classic"
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

    # 5. UI and Interaction State
    timer = ChessTimer(time_limit_seconds=300)
    mode_selector_open: bool = False
    selected_square: Optional[chess.Square] = None
    legal_destinations: List[chess.Square] = []
    dragging: bool = False
    drag_start_square: Optional[chess.Square] = None
    flipped: bool = False  # False: White at bottom; True: Black at bottom
    pending_promotion: Optional[Tuple[chess.Square, chess.Square]] = None

    Assets.play_sound("game_start")

    def switch_to_mode(mode_name: str) -> None:
        nonlocal current_mode_name, game_state, selected_square, legal_destinations, dragging, drag_start_square, pending_promotion, flipped, mode_selector_open
        if mode_name == "Chess + UNO":
            current_mode_name = "Chess + UNO"
            uno_mode = ChessUnoMode()
            game_state = GameState(mode=uno_mode)
            flipped = uno_mode.board_reversed
        elif mode_name == "Immortal Snail":
            current_mode_name = "Immortal Snail"
            snail_mode = ImmortalSnailMode()
            game_state = GameState(mode=snail_mode)
            flipped = False
        else:
            current_mode_name = "Classic"
            classic_mode = ClassicChessMode()
            game_state = GameState(mode=classic_mode)
            flipped = False

        ChessMatrix.set_active_game_state(game_state)
        selected_square = None
        legal_destinations = []
        dragging = False
        drag_start_square = None
        pending_promotion = None
        mode_selector_open = False
        timer.reset()
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
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        # Update match chess clock countdown
        if not mode_selector_open and not game_state.is_game_over():
            timeout_loser = timer.update(dt)
            if timeout_loser is not None:
                game_state.set_timeout(timeout_loser)
                Assets.play_sound("game_over")
                selected_square = None
                legal_destinations = []
                dragging = False
                drag_start_square = None
                pending_promotion = None

        # In Chess + UNO mode, advance shuffle animation
        if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.SHUFFLING:
            game_state.mode.update_shuffle(game_state)

        # In Chess + UNO mode, sync visual flip with Reverse card state unless manually flipped
        if isinstance(game_state.mode, ChessUnoMode):
            flipped = game_state.mode.board_reversed

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ---------------------------------------------------------
            # MOUSE BUTTON DOWN
            # ---------------------------------------------------------
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 1. Mode Selector Modal Intercept
                if mode_selector_open:
                    c_rect, u_rect, s_rect = renderer.get_mode_selector_rects()
                    p_rects, minus_r, plus_r = renderer.get_mode_selector_timer_rects()
                    if c_rect.collidepoint(event.pos):
                        switch_to_mode("Classic")
                    elif u_rect.collidepoint(event.pos):
                        switch_to_mode("Chess + UNO")
                    elif s_rect.collidepoint(event.pos):
                        switch_to_mode("Immortal Snail")
                    else:
                        t_clicked = False
                        for p_rect, sec in p_rects:
                            if p_rect.collidepoint(event.pos):
                                timer.set_time_limit(sec)
                                Assets.play_sound("move")
                                t_clicked = True
                                break
                        if not t_clicked:
                            if minus_r.collidepoint(event.pos):
                                timer.adjust_custom_minutes(-1)
                                Assets.play_sound("move")
                            elif plus_r.collidepoint(event.pos):
                                timer.adjust_custom_minutes(1)
                                Assets.play_sound("move")
                            else:
                                mode_selector_open = False
                                timer.resume()
                    continue

                # 2. Promotion Modal Intercept
                if pending_promotion is not None:
                    from_sq, to_sq = pending_promotion
                    options = renderer.get_promotion_options(game_state.turn, to_sq, flipped=flipped)
                    option_clicked = False
                    for ptype, btn_rect, _ in options:
                        if btn_rect.collidepoint(event.pos):
                            result = game_state.make_move(from_sq, to_sq, promotion=ptype)
                            if result.success:
                                play_move_sound(result)
                                timer.switch_turn(game_state.turn)
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

                # 3. Check UI Button Clicks
                if renderer.buttons.mode_select.collidepoint(event.pos):
                    mode_selector_open = True
                    timer.pause()
                    continue

                if renderer.buttons.timer_select.collidepoint(event.pos):
                    timer.cycle_preset()
                    Assets.play_sound("move")
                    continue

                if (renderer.buttons.white_clock.collidepoint(event.pos) or renderer.buttons.black_clock.collidepoint(event.pos)) and len(game_state.move_history) == 0:
                    timer.cycle_preset()
                    Assets.play_sound("move")
                    continue

                if renderer.buttons.prev_theme.collidepoint(event.pos):
                    change_theme(-1)
                    continue

                if renderer.buttons.next_theme.collidepoint(event.pos):
                    change_theme(1)
                    continue

                if renderer.buttons.new_game.collidepoint(event.pos):
                    game_state.reset()
                    timer.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    Assets.play_sound("game_start")
                    continue

                if renderer.buttons.flip_board.collidepoint(event.pos):
                    flipped = not flipped
                    if isinstance(game_state.mode, ChessUnoMode):
                        game_state.mode.board_reversed = flipped
                    continue

                if renderer.buttons.sound_toggle.collidepoint(event.pos):
                    Assets.toggle_sound()
                    continue

                # Chess + UNO: Draw Card button or Deck click
                if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.AWAITING_DRAW:
                    if (
                        renderer.buttons.draw_card.collidepoint(event.pos)
                        or renderer.buttons.deck_card.collidepoint(event.pos)
                    ):
                        game_state.mode.trigger_draw(game_state, animate=True)
                        continue

                # Immortal Snail: Target King selection before game start
                if isinstance(game_state.mode, ImmortalSnailMode) and game_state.mode.total_legal_moves == 0:
                    if renderer.buttons.target_white.collidepoint(event.pos):
                        game_state.mode.set_target_color(chess.WHITE)
                        continue
                    elif renderer.buttons.target_black.collidepoint(event.pos):
                        game_state.mode.set_target_color(chess.BLACK)
                        continue

                # 4. Board Square Click
                # In Chess + UNO mode, restrict piece interaction until card is drawn and revealed
                if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase != UnoTurnPhase.CARD_ACTIVE:
                    continue

                clicked_sq = pixel_to_square(
                    event.pos,
                    flipped=flipped,
                    board_x=BOARD_X,
                    board_y=BOARD_Y,
                    square_size=SQUARE_SIZE,
                )

                if clicked_sq is not None:
                    # Case A: Already had a piece selected
                    if selected_square is not None:
                        # Click-to-move destination?
                        if clicked_sq in legal_destinations:
                            if game_state.needs_promotion(selected_square, clicked_sq):
                                pending_promotion = (selected_square, clicked_sq)
                            else:
                                result = game_state.make_move(selected_square, clicked_sq)
                                if result.success:
                                    play_move_sound(result)
                                    timer.switch_turn(game_state.turn)
                                selected_square = None
                                legal_destinations = []
                        else:
                            # Clicked another piece belonging to the active player?
                            piece = game_state.get_piece_at(clicked_sq)
                            if piece is not None and piece.color == game_state.turn:
                                selected_square = clicked_sq
                                legal_destinations = game_state.get_legal_destinations(clicked_sq)
                                dragging = True
                                drag_start_square = clicked_sq
                                if not timer.started and timer.has_timer and not game_state.is_game_over():
                                    timer.start(game_state.turn)
                            else:
                                # Deselect
                                selected_square = None
                                legal_destinations = []

                    # Case B: No piece currently selected
                    else:
                        piece = game_state.get_piece_at(clicked_sq)
                        if piece is not None and piece.color == game_state.turn:
                            selected_square = clicked_sq
                            legal_destinations = game_state.get_legal_destinations(clicked_sq)
                            dragging = True
                            drag_start_square = clicked_sq
                            if not timer.started and timer.has_timer and not game_state.is_game_over():
                                timer.start(game_state.turn)

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
                                    timer.switch_turn(game_state.turn)
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
                    timer.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    Assets.play_sound("game_start")

                elif event.key == pygame.K_t:
                    timer.cycle_preset()
                    Assets.play_sound("move")

                elif event.key == pygame.K_f:
                    flipped = not flipped
                    if isinstance(game_state.mode, ChessUnoMode):
                        game_state.mode.board_reversed = flipped

                elif event.key == pygame.K_RIGHT:
                    change_theme(1)

                elif event.key == pygame.K_LEFT:
                    change_theme(-1)

                elif event.key == pygame.K_m:
                    Assets.toggle_sound()

                elif event.key == pygame.K_SPACE:
                    if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.AWAITING_DRAW:
                        game_state.mode.trigger_draw(game_state, animate=True)

                elif event.key == pygame.K_1 and mode_selector_open:
                    switch_to_mode("Classic")

                elif event.key == pygame.K_2 and mode_selector_open:
                    switch_to_mode("Chess + UNO")

                elif event.key == pygame.K_3 and mode_selector_open:
                    switch_to_mode("Immortal Snail")

                elif event.key == pygame.K_ESCAPE:
                    if mode_selector_open:
                        mode_selector_open = False
                        timer.resume()
                    else:
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

        # 3b. Immortal Snail Entity Overlay
        renderer.draw_snail(game_state, flipped=flipped)

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
            piece_images=piece_images,
            timer=timer,
        )

        # 7. Start Menu / Mode Selector Modal
        if mode_selector_open:
            renderer.draw_mode_selector_modal(mouse_pos, timer=timer)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
