
# main.py

import pygame
import ChessMatrix
import Assets

pygame.init()

# Window setup
WINDOW_SIZE = 900
BOARD_X = 50
BOARD_Y = 50
SQUARE_SIZE = 100
BOARD_SIZE = SQUARE_SIZE * 8

screen = pygame.display.set_mode(
    (WINDOW_SIZE, WINDOW_SIZE)
)
pygame.display.set_caption("Chess")

clock = pygame.time.Clock()
FPS = 60

# Load images after initializing the display.
board_image, piece_images = Assets.load_assets()

# Drag-and-drop state
selected_piece = None
selected_pos = None
dragging = False


def get_square(mouse_pos):
    """Convert mouse coordinates to (row, col)."""

    mouse_x, mouse_y = mouse_pos

    col = (mouse_x - BOARD_X) // SQUARE_SIZE
    row = (mouse_y - BOARD_Y) // SQUARE_SIZE

    if ChessMatrix.inside_board(row, col):
        return row, col

    return None


def get_piece_position(row, col):
    """Return the top-left position for a centered piece sprite."""

    square_x = BOARD_X + col * SQUARE_SIZE
    square_y = BOARD_Y + row * SQUARE_SIZE

    offset = (SQUARE_SIZE - Assets.PIECE_SIZE) // 2

    return square_x + offset, square_y + offset


def draw_pieces():
    """Draw every piece except the one being dragged."""

    for row in range(8):
        for col in range(8):
            piece = ChessMatrix.matrix[row][col]

            if piece is None:
                continue

            if dragging and selected_pos == (row, col):
                continue

            image = piece_images[piece]
            position = get_piece_position(row, col)

            screen.blit(image, position)


def handle_mouse_down(mouse_pos):
    global selected_piece, selected_pos, dragging

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
    global selected_piece, selected_pos, dragging

    if not dragging:
        return

    target = get_square(mouse_pos)

    if target is not None:
        ChessMatrix.move_piece(selected_pos, target)

    # Reset drag state even if the move was illegal.
    selected_piece = None
    selected_pos = None
    dragging = False


running = True

while running:
    # Process ALL events inside the event loop.
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

    # Draw the frame.
    screen.fill((40, 40, 40))

    screen.blit(board_image, (BOARD_X, BOARD_Y))

    draw_pieces()

    # Draw the selected sprite under the mouse.
    if dragging and selected_piece is not None:
        image = piece_images[selected_piece]
        rect = image.get_rect(
            center=pygame.mouse.get_pos()
        )
        screen.blit(image, rect)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
