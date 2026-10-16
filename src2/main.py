
# main.py

import pygame
import Assets
import ChessMatrix

pygame.init()

# ============================================================
# 1. WINDOW AND BOARD CONFIGURATION
# ============================================================

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900

BOARD_X = 50
BOARD_Y = 50
SQUARE_SIZE = 100
BOARD_SIZE = SQUARE_SIZE * 8

PANEL_X = 900
PANEL_WIDTH = 270

BACKGROUND_COLOR = (35, 38, 44)
PANEL_COLOR = (48, 52, 60)
TEXT_COLOR = (240, 240, 240)
BUTTON_COLOR = (75, 85, 100)
BUTTON_HOVER_COLOR = (100, 115, 135)
ACCENT_COLOR = (100, 180, 130)

screen = pygame.display.set_mode(
    (WINDOW_WIDTH, WINDOW_HEIGHT)
)
pygame.display.set_caption("Chess")

clock = pygame.time.Clock()
FPS = 60

font = pygame.font.SysFont("arial", 22)
small_font = pygame.font.SysFont("arial", 16)
title_font = pygame.font.SysFont("arial", 28, bold=True)


# ============================================================
# 2. LOAD ASSETS
# ============================================================

board_image, piece_images = Assets.load_assets()

available_packs = Assets.get_available_packs()

if not available_packs:
    raise RuntimeError(
        "No asset packs found. Check your assets folder."
    )

active_pack_index = available_packs.index(
    Assets.get_active_asset_pack()
)


# ============================================================
# 3. DRAG-AND-DROP STATE
# ============================================================

selected_piece = None
selected_pos = None
dragging = False

# These positions are used to highlight the selected square.
last_move = None


# ============================================================
# 4. UI HELPERS
# ============================================================

def draw_text(text, x, y, font_object=font, color=TEXT_COLOR):
    image = font_object.render(
        str(text), True, color
    )
    screen.blit(image, (x, y))


def draw_button(text, rect, mouse_pos):
    hovered = rect.collidepoint(mouse_pos)

    color = BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR

    pygame.draw.rect(
        screen, color, rect, border_radius=8
    )

    pygame.draw.rect(
        screen, (110, 120, 135), rect,
        width=1, border_radius=8
    )

    label = font.render(text, True, TEXT_COLOR)
    label_rect = label.get_rect(center=rect.center)
    screen.blit(label, label_rect)


# Panel button positions.
previous_button = pygame.Rect(PANEL_X, 250, 65, 45)
next_button = pygame.Rect(PANEL_X + 205, 250, 65, 45)
move_sound_button = pygame.Rect(PANEL_X, 420, PANEL_WIDTH, 42)
capture_sound_button = pygame.Rect(PANEL_X, 475, PANEL_WIDTH, 42)


def change_asset_pack(direction):
    """Switch to the previous or next available theme."""

    global active_pack_index
    global board_image, piece_images

    if not available_packs:
        return

    new_index = (
        active_pack_index + direction
    ) % len(available_packs)

    pack_name = available_packs[new_index]

    # Load first, then update the selected index.
    new_board, new_pieces = Assets.switch_asset_pack(
        pack_name
    )

    board_image = new_board
    piece_images = new_pieces
    active_pack_index = new_index


# ============================================================
# 5. BOARD COORDINATES
# ============================================================

def get_square(mouse_pos):
    """Convert mouse coordinates into a board row and column."""

    mouse_x, mouse_y = mouse_pos

    col = (mouse_x - BOARD_X) // SQUARE_SIZE
    row = (mouse_y - BOARD_Y) // SQUARE_SIZE

    if ChessMatrix.inside_board(row, col):
        return row, col

    return None


def get_piece_position(row, col, image):
    """Center a piece within its board square."""

    square_x = BOARD_X + col * SQUARE_SIZE
    square_y = BOARD_Y + row * SQUARE_SIZE

    x = square_x + (
        SQUARE_SIZE - image.get_width()
    ) // 2

    y = square_y + (
        SQUARE_SIZE - image.get_height()
    ) // 2

    return x, y


# ============================================================
# 6. DRAW BOARD AND PIECES
# ============================================================

def draw_board():
    screen.blit(board_image, (BOARD_X, BOARD_Y))

    # Highlight the selected square.
    if selected_pos is not None:
        row, col = selected_pos

        rect = pygame.Rect(
            BOARD_X + col * SQUARE_SIZE,
            BOARD_Y + row * SQUARE_SIZE,
            SQUARE_SIZE,
            SQUARE_SIZE
        )

        overlay = pygame.Surface(
            (SQUARE_SIZE, SQUARE_SIZE),
            pygame.SRCALPHA
        )
        overlay.fill((255, 220, 0, 70))
        screen.blit(overlay, rect.topleft)

    # Highlight the last successfully completed move.
    if last_move is not None:
        for row, col in last_move:
            rect = pygame.Rect(
                BOARD_X + col * SQUARE_SIZE,
                BOARD_Y + row * SQUARE_SIZE,
                SQUARE_SIZE,
                SQUARE_SIZE
            )

            overlay = pygame.Surface(
                (SQUARE_SIZE, SQUARE_SIZE),
                pygame.SRCALPHA
            )
            overlay.fill((50, 200, 100, 55))
            screen.blit(overlay, rect.topleft)


def draw_pieces():
    for row in range(8):
        for col in range(8):

            piece = ChessMatrix.matrix[row][col]

            if piece is None:
                continue

            # Hide the original sprite while dragging it.
            if dragging and selected_pos == (row, col):
                continue

            image = piece_images[piece]

            position = get_piece_position(
                row, col, image
            )

            screen.blit(image, position)


# ============================================================
# 7. DRAW RIGHT-HAND PANEL
# ============================================================

def draw_panel(mouse_pos):
    panel_rect = pygame.Rect(
        PANEL_X - 15, 0,
        WINDOW_WIDTH - PANEL_X + 15,
        WINDOW_HEIGHT
    )

    pygame.draw.rect(
        screen, PANEL_COLOR, panel_rect
    )

    # Header
    draw_text(
        "CHESS SETTINGS",
        PANEL_X, 55,
        title_font
    )

    pygame.draw.line(
        screen, (100, 105, 115),
        (PANEL_X, 100),
        (PANEL_X + PANEL_WIDTH, 100),
        2
    )

    # Asset pack section
    draw_text(
        "Piece & Board Theme",
        PANEL_X, 145
    )

    draw_text(
        f"Theme {active_pack_index + 1} of {len(available_packs)}",
        PANEL_X, 190,
        small_font, (190, 195, 205)
    )

    # Theme name
    pack_name = Assets.get_active_asset_pack()

    draw_text(
        pack_name,
        PANEL_X, 215,
        small_font, ACCENT_COLOR
    )

    draw_button(
        "< Prev", previous_button, mouse_pos
    )

    draw_button(
        "Next >", next_button, mouse_pos
    )

    # Sound section
    pygame.draw.line(
        screen, (100, 105, 115),
        (PANEL_X, 320),
        (PANEL_X + PANEL_WIDTH, 320),
        2
    )

    draw_text(
        "Sound Preview",
        PANEL_X, 355
    )

    draw_button(
        "Test Move Sound",
        move_sound_button,
        mouse_pos
    )

    draw_button(
        "Test Capture Sound",
        capture_sound_button,
        mouse_pos
    )

    # Instructions
    pygame.draw.line(
        screen, (100, 105, 115),
        (PANEL_X, 550),
        (PANEL_X + PANEL_WIDTH, 550),
        2
    )

    draw_text("Controls", PANEL_X, 580)

    instructions = [
        "1. Click a piece.",
        "2. Hold and drag it.",
        "3. Release on a square.",
        "",
        "Invalid moves are rejected.",
        "Theme changes keep the",
        "current board position."
    ]

    for index, line in enumerate(instructions):
        draw_text(
            line,
            PANEL_X,
            620 + index * 25,
            small_font
        )


# ============================================================
# 8. MOUSE INPUT
# ============================================================

def handle_mouse_down(mouse_pos):
    global selected_piece, selected_pos, dragging

    # Check whether a theme button was clicked.
    if previous_button.collidepoint(mouse_pos):
        change_asset_pack(-1)
        return

    if next_button.collidepoint(mouse_pos):
        change_asset_pack(1)
        return

    # Sound preview buttons.
    if move_sound_button.collidepoint(mouse_pos):
        Assets.play_sound("move")
        return

    if capture_sound_button.collidepoint(mouse_pos):
        Assets.play_sound("capture")
        return

    # Otherwise, attempt to select a chess piece.
    square = get_square(mouse_pos)

    if square is None:
        return

    row, col = square
    piece = ChessMatrix.matrix[row][col]

    if piece is not None:
        selected_piece = piece
        selected_pos = square
        dragging = True


def handle_mouse_up(mouse_pos):
    global selected_piece, selected_pos
    global dragging, last_move

    if not dragging:
        return

    target = get_square(mouse_pos)

    if target is not None:
        source = selected_pos
        target_piece = ChessMatrix.matrix[
            target[0]
        ][target[1]]

        moved = ChessMatrix.move_piece(
            source, target
        )

        if moved:
            last_move = (source, target)

            if target_piece is not None:
                Assets.play_sound("capture")
            else:
                Assets.play_sound("move")

        else:
            Assets.play_sound("invalid")

    # Reset drag state even when the move fails.
    selected_piece = None
    selected_pos = None
    dragging = False


# ============================================================
# 9. MAIN GAME LOOP
# ============================================================

running = True

while running:

    mouse_pos = pygame.mouse.get_pos()

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            handle_mouse_down(event.pos)

        elif (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
        ):
            handle_mouse_up(event.pos)

        elif event.type == pygame.KEYDOWN:

            # Optional keyboard theme switching.
            if event.key == pygame.K_RIGHT:
                change_asset_pack(1)

            elif event.key == pygame.K_LEFT:
                change_asset_pack(-1)

    # Draw the complete frame.
    screen.fill(BACKGROUND_COLOR)

    draw_board()
    draw_pieces()
    draw_panel(mouse_pos)

    # Draw the dragged piece at the cursor.
    if dragging and selected_piece is not None:

        image = piece_images[selected_piece]

        rect = image.get_rect(
            center=pygame.mouse.get_pos()
        )

        screen.blit(image, rect)

    pygame.display.flip()
    clock.tick(FPS)


pygame.quit()
