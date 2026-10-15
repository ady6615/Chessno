
# ChessMatrix.py

EMPTY = None

# Keep your original board orientation.
# White starts at the top; black starts at the bottom.
matrix = [
    ["wr", "wk", "wb", "wa", "wq", "wb", "wk", "wr"],
    ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
    ["br", "bk", "bb", "bq", "ba", "bb", "bk", "br"],
]


def inside_board(row, col):
    return 0 <= row < 8 and 0 <= col < 8


def path_clear(start, end):
    """Check whether every square between two positions is empty."""

    r1, c1 = start
    r2, c2 = end

    row_step = (r2 > r1) - (r2 < r1)
    col_step = (c2 > c1) - (c2 < c1)

    row = r1 + row_step
    col = c1 + col_step

    while (row, col) != (r2, c2):
        if matrix[row][col] is not EMPTY:
            return False

        row += row_step
        col += col_step

    return True


def is_valid_move(start, end):
    """Validate basic piece movement and captures.

    This does not yet check whether the king is in check.
    """

    r1, c1 = start
    r2, c2 = end

    if not inside_board(r1, c1) or not inside_board(r2, c2):
        return False

    if start == end:
        return False

    piece = matrix[r1][c1]
    target = matrix[r2][c2]

    if piece is EMPTY:
        return False

    # A piece cannot capture another piece of its own color.
    if target is not EMPTY and target[0] == piece[0]:
        return False

    color = piece[0]
    kind = piece[1]

    dr = r2 - r1
    dc = c2 - c1

    # ROOK: horizontal or vertical movement.
    if kind == "r":
        if dr != 0 and dc != 0:
            return False

        return path_clear(start, end)

    # BISHOP: diagonal movement.
    elif kind == "b":
        if abs(dr) != abs(dc):
            return False

        return path_clear(start, end)

    # QUEEN: rook + bishop movement.
    elif kind == "q":
        straight = dr == 0 or dc == 0
        diagonal = abs(dr) == abs(dc)

        if not straight and not diagonal:
            return False

        return path_clear(start, end)

    # KNIGHT: L-shaped movement; can jump over pieces.
    elif kind == "k":
        return (abs(dr), abs(dc)) in [(2, 1), (1, 2)]

    # KING: one square in any direction.
    elif kind == "a":
        return max(abs(dr), abs(dc)) == 1

    # PAWN: forward movement and diagonal captures.
    elif kind == "p":
        direction = 1 if color == "w" else -1
        starting_row = 1 if color == "w" else 6

        # Move forward by one square.
        if dc == 0 and dr == direction:
            return target is EMPTY

        # Move forward by two squares from starting row.
        if (
            dc == 0
            and r1 == starting_row
            and dr == 2 * direction
            and target is EMPTY
        ):
            middle_row = r1 + direction
            return matrix[middle_row][c1] is EMPTY

        # Capture diagonally by one square.
        if (
            abs(dc) == 1
            and dr == direction
            and target is not EMPTY
        ):
            return target[0] != color

        return False

    return False


def move_piece(start, end):
    """Move a piece if the basic movement rules allow it."""

    if not is_valid_move(start, end):
        return False

    r1, c1 = start
    r2, c2 = end

    matrix[r2][c2] = matrix[r1][c1]
    matrix[r1][c1] = EMPTY

    return True
