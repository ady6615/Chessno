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
import random
from pathlib import Path
from typing import Optional, Tuple, List
import pygame
import chess
from ai_bot import ChessBotController, BotDifficulty

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
from game_engine import GameState, ClassicChessMode, MoveResult
from uno_engine import ChessUnoMode, UnoTurnPhase
from snail_engine import ImmortalSnailMode
from queen_pawn_engine import QueenPawnMode
from rook_dash_engine import RookDashMode
from bishop_dash_engine import BishopDashMode
from hero_mode_engine import HeroMode
from timer import ChessTimer
from renderer import ChessRenderer, BG_COLOR
from asset_pack_creator import AssetPackCreatorState, save_asset_pack, sanitize_pack_name

# Window dimensions
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900
PANEL_X = 900
PANEL_WIDTH = 270


def play_move_sound(result, game_state=None) -> None:
    """Trigger the appropriate sound effect based on the move's outcome."""
    if result.is_checkmate or (game_state and game_state.is_game_over()):
        Assets.play_sound("game_over")
    elif result.is_check or (game_state and game_state.is_in_check()):
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
    # 1. Initialize Pygame & Window Management
    pygame.init()
    VIRTUAL_WIDTH = WINDOW_WIDTH
    VIRTUAL_HEIGHT = WINDOW_HEIGHT
    windowed_size = (VIRTUAL_WIDTH, VIRTUAL_HEIGHT)
    is_fullscreen: bool = False

    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
    pygame.display.set_caption("Chessno - Chess + UNO")
    virtual_screen = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
    clock = pygame.time.Clock()
    FPS = 60

    def toggle_fullscreen() -> None:
        nonlocal is_fullscreen, screen, virtual_screen
        is_fullscreen = not is_fullscreen
        if is_fullscreen:
            # Switch to desktop resolution borderless fullscreen
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
        cur_w, cur_h = screen.get_size()
        virtual_screen = pygame.Surface((cur_w, cur_h))
        renderer.screen = virtual_screen
        renderer.update_layout(cur_w, cur_h, is_fullscreen=is_fullscreen)

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

    # 4. Initialize Renderer (Draws directly to high-res virtual_screen)
    renderer = ChessRenderer(
        screen=virtual_screen,
        board_x=BOARD_X,
        board_y=BOARD_Y,
        square_size=SQUARE_SIZE,
        panel_x=PANEL_X,
        panel_width=PANEL_WIDTH,
    )

    # 5. UI and Interaction State
    timer = ChessTimer(time_limit_seconds=300)
    bot_controller = ChessBotController(difficulty=BotDifficulty.CASUAL)
    mode_selector_open: bool = False
    asset_creator_state = AssetPackCreatorState()
    asset_creator_open: bool = False
    selected_square: Optional[chess.Square] = None
    legal_destinations: List[chess.Square] = []
    dragging: bool = False
    drag_start_square: Optional[chess.Square] = None
    flipped: bool = False  # False: White at bottom; True: Black at bottom
    pending_promotion: Optional[Tuple[chess.Square, chess.Square]] = None

    Assets.play_sound("game_start")
    renderer.trigger_start_bounce()

    def handle_uno_reverse(old_turn: chess.Color, new_turn: chess.Color) -> None:
        nonlocal flipped, selected_square, legal_destinations, dragging, drag_start_square, pending_promotion
        # 1. Swap sides in singleplayer bot mode
        if bot_controller.enabled:
            bot_controller.swap_sides()

        # 2. Sync visual table rotation with UnoMode state
        if isinstance(game_state.mode, ChessUnoMode):
            flipped = game_state.mode.board_reversed

        # 3. Switch active timer clock to match the new turn
        if timer.has_timer and timer.started:
            timer.switch_turn(game_state.turn)

        # 4. Clear interactive drag/selection states
        selected_square = None
        legal_destinations = []
        dragging = False
        drag_start_square = None
        pending_promotion = None

    def switch_to_mode(mode_name: str) -> None:
        nonlocal current_mode_name, game_state, selected_square, legal_destinations, dragging, drag_start_square, pending_promotion, flipped, mode_selector_open
        bot_controller.cancel_thinking()
        end_pieces = {sq: game_state.get_piece_at(sq) for sq in chess.SQUARES if game_state.get_piece_at(sq) is not None}
        if mode_name == "Chess + UNO":
            current_mode_name = "Chess + UNO"
            uno_mode = ChessUnoMode(on_reverse_card=handle_uno_reverse)
            if bot_controller.player_color == chess.BLACK:
                uno_mode.board_reversed = True
            game_state = GameState(mode=uno_mode)
            flipped = uno_mode.board_reversed
        elif mode_name == "Immortal Snail":
            current_mode_name = "Immortal Snail"
            snail_mode = ImmortalSnailMode()
            game_state = GameState(mode=snail_mode)
            flipped = (bot_controller.player_color == chess.BLACK)
        elif mode_name in ("Queen Pawn", "Queen Pawn Game"):
            current_mode_name = "Queen Pawn"
            qp_mode = QueenPawnMode()
            game_state = GameState(mode=qp_mode)
            flipped = (bot_controller.player_color == chess.BLACK)
        elif mode_name in ("Rook Dash", "rook dash"):
            current_mode_name = "Rook Dash"
            rd_mode = RookDashMode()
            game_state = GameState(mode=rd_mode)
            flipped = (bot_controller.player_color == chess.BLACK)
        elif mode_name in ("Bishop Dash", "bishop dash"):
            current_mode_name = "Bishop Dash"
            bd_mode = BishopDashMode()
            game_state = GameState(mode=bd_mode)
            flipped = (bot_controller.player_color == chess.BLACK)
        elif mode_name in ("Hero Mode", "hero mode"):
            current_mode_name = "Hero Mode"
            hm_mode = HeroMode()
            game_state = GameState(mode=hm_mode)
            flipped = (bot_controller.player_color == chess.BLACK)
        else:
            current_mode_name = "Classic"
            classic_mode = ClassicChessMode()
            game_state = GameState(mode=classic_mode)
            flipped = (bot_controller.player_color == chess.BLACK)

        ChessMatrix.set_active_game_state(game_state)
        selected_square = None
        legal_destinations = []
        dragging = False
        drag_start_square = None
        pending_promotion = None
        mode_selector_open = False
        timer.reset()
        renderer.cancel_rook_dash()
        Assets.play_sound("game_start")
        renderer.trigger_reset_return(end_pieces, game_state, piece_images, flipped=flipped)

    def check_and_trigger_rook_dash(
        moving_piece: Optional[chess.Piece],
        from_sq: chess.Square,
        to_sq: chess.Square,
        result: MoveResult,
    ) -> None:
        if not result.success or moving_piece is None:
            return
        mode_name = getattr(game_state.mode, "name", "")
        if (
            mode_name == "Rook Dash"
            and moving_piece.piece_type == chess.ROOK
        ):
            pcode = piece_to_code(moving_piece) or ("wr" if moving_piece.color == chess.WHITE else "br")
            renderer.trigger_rook_dash(
                from_sq=from_sq,
                to_sq=to_sq,
                piece_code=pcode,
                piece_images=piece_images,
                is_capture=result.is_capture,
                flipped=flipped,
            )
            Assets.play_sound("dash")
        elif (
            mode_name == "Bishop Dash"
            and moving_piece.piece_type == chess.BISHOP
        ):
            pcode = piece_to_code(moving_piece) or ("wb" if moving_piece.color == chess.WHITE else "bb")
            renderer.trigger_bishop_dash(
                from_sq=from_sq,
                to_sq=to_sq,
                piece_code=pcode,
                piece_images=piece_images,
                is_capture=result.is_capture,
                flipped=flipped,
            )
            Assets.play_sound("dash")

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
        renderer.update_reset_return(dt)
        renderer.update_start_bounce(dt)
        renderer.update_rook_dash(dt)
        if asset_creator_open:
            asset_creator_state.update(dt)

        # Ensure virtual_screen and renderer layout dynamically match current screen dimensions
        disp_w, disp_h = screen.get_size()
        if virtual_screen.get_size() != (disp_w, disp_h):
            virtual_screen = pygame.Surface((disp_w, disp_h))
            renderer.screen = virtual_screen
            renderer.update_layout(disp_w, disp_h, is_fullscreen=is_fullscreen)

        def screen_to_virtual(pos: Tuple[int, int]) -> Tuple[int, int]:
            return pos

        mouse_pos = pygame.mouse.get_pos()

        # Update match chess clock countdown
        if not mode_selector_open and not asset_creator_open and not game_state.is_game_over():
            timeout_loser = timer.update(dt)
            if timeout_loser is not None:
                game_state.set_timeout(timeout_loser)
                Assets.play_sound("game_over")
                selected_square = None
                legal_destinations = []
                dragging = False
                drag_start_square = None
                pending_promotion = None
        # AI Bot Thinking & Move Execution (Singleplayer mode)
        if (
            not mode_selector_open
            and not asset_creator_open
            and pending_promotion is None
            and not game_state.is_game_over()
            and not renderer.is_dash_animating()
            and bot_controller.is_bot_turn(game_state)
        ):
            bot_move, trigger_draw = bot_controller.update(dt, game_state)
            if trigger_draw:
                game_state.mode.trigger_draw(game_state, animate=True)
            elif bot_move is not None:
                promo = bot_move.promotion
                if promo is None and game_state.needs_promotion(bot_move.from_square, bot_move.to_square):
                    promo = getattr(game_state.mode, "auto_promotion_piece", chess.QUEEN)
                moving_piece = game_state.get_piece_at(bot_move.from_square)
                result = game_state.make_move(bot_move.from_square, bot_move.to_square, promotion=promo)
                if result.success:
                    check_and_trigger_rook_dash(moving_piece, bot_move.from_square, bot_move.to_square, result)
                    play_move_sound(result, game_state)
                    timer.switch_turn(game_state.turn)
                    if not timer.started and timer.has_timer and not game_state.is_game_over():
                        timer.start(game_state.turn)
                else:
                    # Fallback if bot move was rejected by mod-specific constraints
                    all_valid = []
                    for sq in chess.SQUARES:
                        all_valid.extend(game_state.get_legal_moves_from(sq))
                    if all_valid:
                        fb_m = random.choice(all_valid)
                        fb_promo = fb_m.promotion or (getattr(game_state.mode, "auto_promotion_piece", chess.QUEEN) if game_state.needs_promotion(fb_m.from_square, fb_m.to_square) else None)
                        fb_piece = game_state.get_piece_at(fb_m.from_square)
                        res2 = game_state.make_move(fb_m.from_square, fb_m.to_square, promotion=fb_promo)
                        if res2.success:
                            check_and_trigger_rook_dash(fb_piece, fb_m.from_square, fb_m.to_square, res2)
                            play_move_sound(res2, game_state)
                            timer.switch_turn(game_state.turn)

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

            elif event.type == pygame.VIDEORESIZE:
                if not is_fullscreen:
                    windowed_size = (max(800, event.w), max(600, event.h))
                    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                    cur_w, cur_h = screen.get_size()
                    virtual_screen = pygame.Surface((cur_w, cur_h))
                    renderer.screen = virtual_screen
                    renderer.update_layout(cur_w, cur_h, is_fullscreen=False)
                continue

            # ---------------------------------------------------------
            # MOUSE BUTTON DOWN
            # ---------------------------------------------------------
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                event_pos = screen_to_virtual(event.pos)

                # 0. Fullscreen Button Intercept
                if renderer.buttons.fullscreen.collidepoint(event_pos):
                    toggle_fullscreen()
                    continue

                # 0b. Asset Pack Creator Modal Intercept
                if asset_creator_open:
                    c_rects = renderer.get_asset_pack_creator_rects()
                    if c_rects["close"].collidepoint(event_pos) or c_rects["cancel"].collidepoint(event_pos):
                        asset_creator_open = False
                        timer.resume()
                        continue

                    if c_rects["name_input"].collidepoint(event_pos):
                        asset_creator_state.name_focused = True
                        continue
                    else:
                        asset_creator_state.name_focused = False

                    if c_rects["import_folder"].collidepoint(event_pos):
                        asset_creator_state.browse_folder_and_auto_match()
                        continue

                    if c_rects["reset_all"].collidepoint(event_pos):
                        asset_creator_state.reset(default_piece_images=piece_images)
                        continue

                    clicked_piece = False
                    for code, b_rect in c_rects["browse"].items():
                        if b_rect.collidepoint(event_pos):
                            asset_creator_state.browse_for_piece(code)
                            clicked_piece = True
                            break
                    if clicked_piece:
                        continue

                    clicked_clr = False
                    for code, clr_r in c_rects["clear"].items():
                        if clr_r.collidepoint(event_pos):
                            asset_creator_state.clear_piece_image(code, default_piece_images=piece_images)
                            clicked_clr = True
                            break
                    if clicked_clr:
                        continue

                    if c_rects["save"].collidepoint(event_pos):
                        ok, msg = save_asset_pack(
                            asset_creator_state.pack_name,
                            asset_creator_state.piece_paths,
                            default_piece_images=piece_images,
                        )
                        if ok:
                            available_packs = Assets.get_available_packs()
                            clean_p_name = sanitize_pack_name(asset_creator_state.pack_name)
                            if clean_p_name in available_packs:
                                new_board, new_pieces = Assets.switch_asset_pack(clean_p_name)
                                board_image = new_board
                                piece_images = new_pieces
                                active_pack_index = available_packs.index(clean_p_name)
                            Assets.play_sound("game_start")
                            asset_creator_open = False
                            timer.resume()
                        else:
                            asset_creator_state.status_message = msg
                            asset_creator_state.status_is_error = True
                        continue

                    # If clicked inside modal, consume event
                    if c_rects["modal"].collidepoint(event_pos):
                        continue
                    else:
                        # Clicked outside modal -> dismiss
                        asset_creator_open = False
                        timer.resume()
                        continue

                # 1. Mode Selector Modal Intercept
                if mode_selector_open:
                    c_rect, u_rect, s_rect, qp_rect, rd_rect, bd_rect, hm_rect = renderer.get_mode_selector_rects()
                    p_rects, minus_r, plus_r = renderer.get_mode_selector_timer_rects()
                    vs_bot_r, vs_local_r, diff_rects, side_rects, start_game_r = renderer.get_mode_selector_ai_rects()

                    if c_rect.collidepoint(event_pos):
                        switch_to_mode("Classic")
                    elif u_rect.collidepoint(event_pos):
                        switch_to_mode("Chess + UNO")
                    elif s_rect.collidepoint(event_pos):
                        switch_to_mode("Immortal Snail")
                    elif qp_rect.collidepoint(event_pos):
                        switch_to_mode("Queen Pawn")
                    elif rd_rect.collidepoint(event_pos):
                        switch_to_mode("Rook Dash")
                    elif bd_rect.collidepoint(event_pos):
                        switch_to_mode("Bishop Dash")
                    elif hm_rect.collidepoint(event_pos):
                        switch_to_mode("Hero Mode")
                    elif vs_bot_r.collidepoint(event_pos):
                        bot_controller.enabled = True
                        Assets.play_sound("move")
                    elif vs_local_r.collidepoint(event_pos):
                        bot_controller.enabled = False
                        Assets.play_sound("move")
                    elif side_rects[0].collidepoint(event_pos):  # White
                        bot_controller.set_player_color(chess.WHITE)
                        flipped = False
                        Assets.play_sound("move")
                    elif side_rects[1].collidepoint(event_pos):  # Random
                        c = random.choice([chess.WHITE, chess.BLACK])
                        bot_controller.set_player_color(c)
                        flipped = (c == chess.BLACK)
                        Assets.play_sound("move")
                    elif side_rects[2].collidepoint(event_pos):  # Black
                        bot_controller.set_player_color(chess.BLACK)
                        flipped = True
                        Assets.play_sound("move")
                    elif start_game_r.collidepoint(event_pos):
                        mode_selector_open = False
                        timer.resume()
                        Assets.play_sound("game_start")
                        renderer.trigger_start_bounce()
                    else:
                        d_clicked = False
                        for d_r, diff in diff_rects:
                            if d_r.collidepoint(event_pos):
                                bot_controller.set_difficulty(diff)
                                bot_controller.enabled = True
                                Assets.play_sound("move")
                                d_clicked = True
                                break
                        if not d_clicked:
                            t_clicked = False
                            for p_rect, sec in p_rects:
                                if p_rect.collidepoint(event_pos):
                                    timer.set_time_limit(sec)
                                    Assets.play_sound("move")
                                    t_clicked = True
                                    break
                            if not t_clicked:
                                if minus_r.collidepoint(event_pos):
                                    timer.adjust_custom_minutes(-1)
                                    Assets.play_sound("move")
                                elif plus_r.collidepoint(event_pos):
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
                        if btn_rect.collidepoint(event_pos):
                            result = game_state.make_move(from_sq, to_sq, promotion=ptype)
                            if result.success:
                                play_move_sound(result, game_state)
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

                # 2b. Game Over Winning Popup Restart Click
                if game_state.is_game_over() and not mode_selector_open:
                    restart_btn = renderer.get_game_over_restart_rect()
                    if restart_btn.collidepoint(event_pos):
                        bot_controller.cancel_thinking()
                        end_pieces = {sq: game_state.get_piece_at(sq) for sq in chess.SQUARES if game_state.get_piece_at(sq) is not None}
                        game_state.reset()
                        timer.reset()
                        selected_square = None
                        legal_destinations = []
                        dragging = False
                        drag_start_square = None
                        pending_promotion = None
                        if bot_controller.player_color == chess.BLACK:
                            flipped = True
                        renderer.cancel_rook_dash()
                        Assets.play_sound("game_start")
                        renderer.trigger_reset_return(end_pieces, game_state, piece_images, flipped=flipped)
                        continue

                # 3. Check UI Button Clicks
                if renderer.buttons.mode_select.collidepoint(event_pos):
                    mode_selector_open = True
                    timer.pause()
                    continue

                if renderer.buttons.bot_toggle.collidepoint(event_pos):
                    bot_controller.toggle_enabled()
                    Assets.play_sound("move")
                    continue

                if renderer.buttons.bot_difficulty.collidepoint(event_pos) or renderer.buttons.bot_quick_toggle.collidepoint(event_pos):
                    bot_controller.cycle_difficulty(1)
                    Assets.play_sound("move")
                    continue

                if renderer.buttons.timer_select.collidepoint(event_pos):
                    timer.cycle_preset()
                    Assets.play_sound("move")
                    continue

                if (renderer.buttons.white_clock.collidepoint(event_pos) or renderer.buttons.black_clock.collidepoint(event_pos)) and len(game_state.move_history) == 0:
                    timer.cycle_preset()
                    Assets.play_sound("move")
                    continue

                if renderer.buttons.create_pack.collidepoint(event_pos):
                    asset_creator_state.reset(default_piece_images=piece_images)
                    asset_creator_open = True
                    timer.pause()
                    continue

                if renderer.buttons.prev_theme.collidepoint(event_pos):
                    change_theme(-1)
                    continue

                if renderer.buttons.next_theme.collidepoint(event_pos):
                    change_theme(1)
                    continue

                if renderer.buttons.new_game.collidepoint(event_pos):
                    bot_controller.cancel_thinking()
                    end_pieces = {sq: game_state.get_piece_at(sq) for sq in chess.SQUARES if game_state.get_piece_at(sq) is not None}
                    game_state.reset()
                    timer.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    if bot_controller.player_color == chess.BLACK:
                        flipped = True
                    renderer.cancel_rook_dash()
                    Assets.play_sound("game_start")
                    renderer.trigger_reset_return(end_pieces, game_state, piece_images, flipped=flipped)
                    continue

                if renderer.buttons.flip_board.collidepoint(event_pos):
                    flipped = not flipped
                    if isinstance(game_state.mode, ChessUnoMode):
                        game_state.mode.board_reversed = flipped
                    continue

                if renderer.buttons.sound_toggle.collidepoint(event_pos):
                    Assets.toggle_sound()
                    continue

                # Chess + UNO: Draw Card button or Deck click
                if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.AWAITING_DRAW:
                    if (
                        renderer.buttons.draw_card.collidepoint(event_pos)
                        or renderer.buttons.deck_card.collidepoint(event_pos)
                    ):
                        game_state.mode.trigger_draw(game_state, animate=True)
                        continue

                # Immortal Snail: Target King selection before game start
                if isinstance(game_state.mode, ImmortalSnailMode) and game_state.mode.total_legal_moves == 0:
                    if renderer.buttons.target_white.collidepoint(event_pos):
                        game_state.mode.set_target_color(chess.WHITE)
                        continue
                    elif renderer.buttons.target_black.collidepoint(event_pos):
                        game_state.mode.set_target_color(chess.BLACK)
                        continue

                # 4. Board Square Click
                # In Chess + UNO mode, restrict piece interaction until card is drawn and revealed
                if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase != UnoTurnPhase.CARD_ACTIVE:
                    continue

                # Block player piece interaction when it is the AI Bot's turn
                if bot_controller.is_bot_turn(game_state):
                    continue

                clicked_sq = pixel_to_square(
                    event_pos,
                    flipped=flipped,
                    board_x=renderer.board_x,
                    board_y=renderer.board_y,
                    square_size=renderer.square_size,
                )

                if clicked_sq is not None:
                    if renderer.is_dash_animating():
                        continue
                    if renderer.is_return_animating():
                        renderer.cancel_reset_return()
                        renderer.cancel_start_bounce()
                    elif renderer.is_bounce_animating():
                        renderer.cancel_start_bounce()
                    # Case A: Already had a piece selected
                    if selected_square is not None:
                        # Click-to-move destination?
                        if clicked_sq in legal_destinations:
                            if game_state.needs_promotion(selected_square, clicked_sq):
                                auto_p = getattr(game_state.mode, "auto_promotion_piece", None)
                                if auto_p is not None:
                                    result = game_state.make_move(selected_square, clicked_sq, promotion=auto_p)
                                    if result.success:
                                        play_move_sound(result, game_state)
                                        timer.switch_turn(game_state.turn)
                                    selected_square = None
                                    legal_destinations = []
                                else:
                                    pending_promotion = (selected_square, clicked_sq)
                            else:
                                moving_p = game_state.get_piece_at(selected_square)
                                result = game_state.make_move(selected_square, clicked_sq)
                                if result.success:
                                    check_and_trigger_rook_dash(moving_p, selected_square, clicked_sq, result)
                                    play_move_sound(result, game_state)
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
                event_pos = screen_to_virtual(event.pos)
                if bot_controller.is_bot_turn(game_state):
                    dragging = False
                    drag_start_square = None
                    continue

                if dragging and drag_start_square is not None:
                    target_sq = pixel_to_square(
                        event_pos,
                        flipped=flipped,
                        board_x=renderer.board_x,
                        board_y=renderer.board_y,
                        square_size=renderer.square_size,
                    )

                    # If released on a different square (drag-and-drop move attempt)
                    if target_sq is not None and target_sq != drag_start_square:
                        if target_sq in legal_destinations:
                            if game_state.needs_promotion(drag_start_square, target_sq):
                                auto_p = getattr(game_state.mode, "auto_promotion_piece", None)
                                if auto_p is not None:
                                    result = game_state.make_move(drag_start_square, target_sq, promotion=auto_p)
                                    if result.success:
                                        play_move_sound(result, game_state)
                                        timer.switch_turn(game_state.turn)
                                    selected_square = None
                                    legal_destinations = []
                                else:
                                    pending_promotion = (drag_start_square, target_sq)
                            else:
                                moving_p = game_state.get_piece_at(drag_start_square)
                                result = game_state.make_move(drag_start_square, target_sq)
                                if result.success:
                                    check_and_trigger_rook_dash(moving_p, drag_start_square, target_sq, result)
                                    play_move_sound(result, game_state)
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
                if asset_creator_open:
                    if event.key == pygame.K_ESCAPE and not asset_creator_state.name_focused:
                        asset_creator_open = False
                        timer.resume()
                        continue
                    consumed = asset_creator_state.handle_keydown(event)
                    if consumed:
                        continue
                    continue

                # Fullscreen Shortcuts (F11 or Alt+Enter)
                if event.key == pygame.K_F11:
                    toggle_fullscreen()
                    continue

                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and (event.mod & pygame.KMOD_ALT):
                    toggle_fullscreen()
                    continue

                elif event.key == pygame.K_r:
                    bot_controller.cancel_thinking()
                    end_pieces = {sq: game_state.get_piece_at(sq) for sq in chess.SQUARES if game_state.get_piece_at(sq) is not None}
                    game_state.reset()
                    timer.reset()
                    selected_square = None
                    legal_destinations = []
                    dragging = False
                    drag_start_square = None
                    pending_promotion = None
                    if bot_controller.player_color == chess.BLACK:
                        flipped = True
                    renderer.cancel_rook_dash()
                    Assets.play_sound("game_start")
                    renderer.trigger_reset_return(end_pieces, game_state, piece_images, flipped=flipped)

                elif event.key == pygame.K_b:
                    bot_controller.cycle_difficulty(1)
                    Assets.play_sound("move")

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

                elif event.key == pygame.K_p and not mode_selector_open and not asset_creator_open:
                    asset_creator_state.reset(default_piece_images=piece_images)
                    asset_creator_open = True
                    timer.pause()

                elif event.key == pygame.K_SPACE:
                    if mode_selector_open:
                        mode_selector_open = False
                        timer.resume()
                        Assets.play_sound("game_start")
                        renderer.trigger_start_bounce()
                    elif isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.AWAITING_DRAW:
                        game_state.mode.trigger_draw(game_state, animate=True)

                elif event.key == pygame.K_1 and mode_selector_open:
                    switch_to_mode("Classic")

                elif event.key == pygame.K_2 and mode_selector_open:
                    switch_to_mode("Chess + UNO")

                elif event.key == pygame.K_3 and mode_selector_open:
                    switch_to_mode("Immortal Snail")

                elif event.key == pygame.K_4 and mode_selector_open:
                    switch_to_mode("Queen Pawn")

                elif event.key == pygame.K_5 and mode_selector_open:
                    switch_to_mode("Rook Dash")

                elif event.key == pygame.K_6 and mode_selector_open:
                    switch_to_mode("Bishop Dash")

                elif event.key == pygame.K_7 and mode_selector_open:
                    switch_to_mode("Hero Mode")

                elif event.key == pygame.K_ESCAPE:
                    if mode_selector_open:
                        mode_selector_open = False
                        timer.resume()
                    elif pending_promotion is not None or selected_square is not None or dragging:
                        pending_promotion = None
                        selected_square = None
                        legal_destinations = []
                        dragging = False
                        drag_start_square = None
                    elif is_fullscreen:
                        toggle_fullscreen()

        # -------------------------------------------------------------
        # DRAWING ROUTINE (Render directly to high-res virtual_screen)
        # -------------------------------------------------------------
        virtual_screen.fill(BG_COLOR)

        # 1. Chessboard background with frame and rank/file coordinates
        renderer.draw_board(board_image, flipped=flipped)

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
            if getattr(game_state.mode, "name", "") == "Hero Mode" and piece and piece.piece_type == chess.QUEEN:
                hero_code = "wh" if piece.color == chess.WHITE else "bh"
                if hero_code in piece_images:
                    code = hero_code
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
            is_fullscreen=is_fullscreen,
            bot_controller=bot_controller,
        )

        # 6b. Winning Title Popup (in the middle of the board with 50% transparency)
        if game_state.is_game_over() and not mode_selector_open:
            renderer.draw_game_over_popup(game_state, mouse_pos=mouse_pos)

        # 7. Start Menu / Mode Selector Modal
        if mode_selector_open:
            renderer.draw_mode_selector_modal(mouse_pos, timer=timer, bot_controller=bot_controller)

        # 7b. Custom Asset Pack Creator Modal
        if asset_creator_open:
            renderer.draw_asset_pack_creator_modal(
                mouse_pos=mouse_pos,
                state=asset_creator_state,
                default_piece_images=piece_images,
            )

        # -------------------------------------------------------------
        # PRESENTATION (Direct 1:1 blit to display)
        # -------------------------------------------------------------
        screen.blit(virtual_screen, (0, 0))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
