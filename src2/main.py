
# main.py

import pygame
import Assets
import ChessMatrix

# Initialize Pygame before loading images.
pygame.init()

# Window and board settings.
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 900

BOARD_X = 50
BOARD_Y = 50

SQUARE_SIZE = 100
BOARD_SIZE = SQUARE_SIZE * 8

screen = pygame.display.set_mode(
    (WINDOW_WIDTH, WINDOW_HEIGHT)
)

pygame.display.set_caption("Chess")
clock = pygame.time.Clock()
FPS = 60

# Load board and piece images.
board_image, piece_images = Assets.load_assets()

# Drag-and-drop variables.
selected_piece = None
selected_pos = None
dragging = False


def get_square(mouse_pos):
    """Convert mouse coordinates into board row and column."""

    mouse_x, mouse_y = mouse_pos

    col = (mouse_x - BOARD_X) // SQUARE_SIZE
    row = (mouse_y - BOARD_Y) // SQUARE_SIZE

    if ChessMatrix.inside_board(row, col):
        return row, col

    return None


def get_piece_position(row, col, image):
    """Center a piece image inside its square."""

    square_x = BOARD_X + col * SQUARE_SIZE
    square_y = BOARD_Y + row * SQUARE_SIZE

    x = square_x + (SQUARE_SIZE - image.get_width()) // 2
    y = square_y + (SQUARE_SIZE - image.get_height()) // 2

    return x, y


def draw_pieces():
    """Draw all pieces except the piece currently being dragged."""

    for row in range(8):
        for col in range(8):

            piece = ChessMatrix.matrix[row][col]

            if piece is None:
                continue

            if dragging and selected_pos == (row, col):
                continue

            image = piece_images[piece]

            position = get_piece_position(
                row, col, image
            )

            screen.blit(image, position)


def handle_mouse_down(mouse_pos):
    """Select a piece when the left mouse button is pressed."""

    global selected_piece, selected_pos, dragging

    square = get_square(mouse_pos)

    if square is None:
        return

    row, col = square
    piece = ChessMatrix.matrix[row][col]

    if piece is not None:
        selected_piece = piece
        selected_pos = (row, col)
        dragging = True


def handle_mouse_up(mouse_pos):
    """Attempt to move the selected piece to the target square."""

    global selected_piece, selected_pos, dragging

    if not dragging:
        return

    target = get_square(mouse_pos)

    if target is not None:
        ChessMatrix.move_piece(selected_pos, target)

    # The matrix remains unchanged if the move is invalid.
    selected_piece = None
    selected_pos = None
    dragging = False


running = True

while running:

    # Handle every event inside the event loop.
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

    # Clear the window.
    screen.fill((40, 40, 40))

    # Draw the board.
    screen.blit(board_image, (BOARD_X, BOARD_Y))

    # Draw pieces in their current matrix positions.
    draw_pieces()

    # Draw the selected piece under the mouse cursor.
    if dragging and selected_piece is not None:

        image = piece_images[selected_piece]

        rect = image.get_rect(
            center=pygame.mouse.get_pos()
        )

        screen.blit(image, rect)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
