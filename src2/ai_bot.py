# ai_bot.py
"""
AI Bot Engine for Chessno Singleplayer Mode.

Features:
- 4 Distinct AI Bot Difficulty Levels:
    1. Novice (Level 1, ~800 Elo): Casual/beginner, plays fast, occasional mistakes.
    2. Casual (Level 2, ~1200 Elo): Solid club level, depth-2 minimax, avoids hanging pieces.
    3. Intermediate (Level 3, ~1600 Elo): Depth-3 alpha-beta + quiescence search, PST positional play.
    4. Master (Level 4, ~2000+ Elo): Depth-4 alpha-beta + quiescence search, tapered eval, king safety.
- Full Piece-Square Tables (PeSTO's standard positional weights for opening & endgame).
- Move ordering via MVV-LVA (Most Valuable Victim - Least Valuable Attacker) + checks + promotions.
- Quiescence search to eliminate the horizon effect during tactical trades.
- Specialized support for game variants:
    - Classic Chess: Full standard FIDE positional & tactical evaluation.
    - Queen Pawn Game: Pawn-protection, pawn-hunting & queen-safety heuristics.
    - Immortal Snail: King evasive routing to evade hunting snails.
    - Chess + UNO: Automatic card draw trigger & multi-move execution.
- Asynchronous, non-blocking background thinking: Pygame maintains rock-solid 60 FPS.
- Natural human-like reaction pacing with live thinking visual feedback.
"""

from enum import Enum
import random
import time
import threading
from typing import Optional, Tuple, List, Dict, Any
import chess

# Centipawn piece valuations
PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# -----------------------------------------------------------------------------
# PeSTO's Piece-Square Tables (mapped from a1=0 to h8=63)
# -----------------------------------------------------------------------------
PAWN_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
]

KNIGHT_PST = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]

BISHOP_PST = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]

ROOK_PST = [
      0,  0,  0,  5,  5,  0,  0,  0,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      5, 10, 10, 10, 10, 10, 10,  5,
      0,  0,  0,  0,  0,  0,  0,  0,
]

QUEEN_PST = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
      0,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]

KING_MIDGAME_PST = [
     20, 30, 10,  0,  0, 10, 30, 20,
     20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
]

KING_ENDGAME_PST = [
    -50,-30,-30,-30,-30,-30,-30,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50,
]

PST_MAP = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}


class BotDifficulty(Enum):
    NOVICE = "Novice"            # Level 1 (~800 Elo)
    CASUAL = "Casual"            # Level 2 (~1200 Elo)
    INTERMEDIATE = "Intermediate"# Level 3 (~1600 Elo)
    MASTER = "Master"            # Level 4 (~2000+ Elo)


BOT_DIFFICULTY_METADATA = {
    BotDifficulty.NOVICE: {
        "level_num": 1,
        "name": "Novice",
        "elo": "800 Elo",
        "badge_color": (60, 205, 145),       # Emerald
        "desc": "Beginner friendly • Occasional tactical oversights",
        "min_delay": 0.45,
        "max_delay": 0.75,
        "depth": 1,
    },
    BotDifficulty.CASUAL: {
        "level_num": 2,
        "name": "Casual",
        "elo": "1200 Elo",
        "badge_color": (56, 189, 248),       # Sky Cyan
        "desc": "Solid club player • Captures free pieces & guards king",
        "min_delay": 0.55,
        "max_delay": 0.90,
        "depth": 2,
    },
    BotDifficulty.INTERMEDIATE: {
        "level_num": 3,
        "name": "Intermediate",
        "elo": "1600 Elo",
        "badge_color": (251, 191, 36),       # Amber Gold
        "desc": "Sharp tactician • Quiescence search & piece-square tables",
        "min_delay": 0.65,
        "max_delay": 1.10,
        "depth": 3,
    },
    BotDifficulty.MASTER: {
        "level_num": 4,
        "name": "Master",
        "elo": "2000+ Elo",
        "badge_color": (217, 70, 239),       # Neon Fuchsia
        "desc": "Deep calculation • Move ordering, king safety & endgame play",
        "min_delay": 0.80,
        "max_delay": 1.40,
        "depth": 4,
    },
}


# -----------------------------------------------------------------------------
# Static Evaluation Engine
# -----------------------------------------------------------------------------

def evaluate_board(board: chess.Board, game_mode: Optional[Any] = None) -> int:
    """
    Evaluate chess board position in centipawns from White's perspective.
    Positive score favored White; Negative favored Black.
    """
    if board.is_checkmate():
        return -30000 if board.turn == chess.WHITE else 30000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    # 1. Queen Pawn Mode Specialized Evaluation
    if game_mode and getattr(game_mode, "name", "") in ("Queen Pawn", "Queen Pawn Game"):
        w_pawns = len(board.pieces(chess.PAWN, chess.WHITE))
        b_pawns = len(board.pieces(chess.PAWN, chess.BLACK))
        w_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = len(board.pieces(chess.QUEEN, chess.BLACK))

        # In Queen Pawn mode: eliminating all enemy pawns wins!
        score = (w_pawns - b_pawns) * 400 + (w_queens - b_queens) * 1200
        # Danger penalty if queen is attacked
        for q_sq in board.pieces(chess.QUEEN, chess.WHITE):
            if board.is_attacked_by(chess.BLACK, q_sq):
                score -= 350
        for q_sq in board.pieces(chess.QUEEN, chess.BLACK):
            if board.is_attacked_by(chess.WHITE, q_sq):
                score += 350
        return score

    # 2. Standard Material & Positional Evaluation
    white_material = 0
    black_material = 0
    white_pst = 0
    black_pst = 0

    # Calculate game phase (0 = pure endgame, 24 = full opening)
    phase = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        cnt = len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK))
        weight = 1 if piece_type in (chess.KNIGHT, chess.BISHOP) else (2 if piece_type == chess.ROOK else 4)
        phase += cnt * weight

    phase = min(24, phase)
    eg_weight = (24 - phase) / 24.0
    mg_weight = 1.0 - eg_weight

    for square, piece in board.piece_map().items():
        val = PIECE_VALUES[piece.piece_type]
        sq_idx = square if piece.color == chess.WHITE else chess.square_mirror(square)

        if piece.piece_type == chess.KING:
            mg_king = KING_MIDGAME_PST[sq_idx]
            eg_king = KING_ENDGAME_PST[sq_idx]
            pst_val = int(mg_king * mg_weight + eg_king * eg_weight)
        else:
            pst_table = PST_MAP.get(piece.piece_type)
            pst_val = pst_table[sq_idx] if pst_table else 0

        if piece.color == chess.WHITE:
            white_material += val
            white_pst += pst_val
        else:
            black_material += val
            black_pst += pst_val

    # 3. Positional adjustments: Bishop pair & Rook on open file
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        white_pst += 30
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        black_pst += 30

    # Rook open files
    for r_sq in board.pieces(chess.ROOK, chess.WHITE):
        f = chess.square_file(r_sq)
        if not any(chess.square_file(p_sq) == f for p_sq in board.pieces(chess.PAWN, chess.WHITE)):
            white_pst += 20
    for r_sq in board.pieces(chess.ROOK, chess.BLACK):
        f = chess.square_file(r_sq)
        if not any(chess.square_file(p_sq) == f for p_sq in board.pieces(chess.PAWN, chess.BLACK)):
            black_pst += 20

    # 4. Immortal Snail evasive heuristics
    if game_mode and getattr(game_mode, "name", "") == "Immortal Snail":
        w_king_sq = board.king(chess.WHITE)
        b_king_sq = board.king(chess.BLACK)
        if hasattr(game_mode, "black_snail") and w_king_sq is not None:
            # Black snail hunts White king
            b_snail_pos = game_mode.black_snail.current_pos
            dist_w = max(abs(chess.square_file(w_king_sq) - b_snail_pos[0]),
                         abs(chess.square_rank(w_king_sq) - b_snail_pos[1]))
            if dist_w <= 1:
                white_pst -= 3000
            elif dist_w == 2:
                white_pst -= 400
        if hasattr(game_mode, "white_snail") and b_king_sq is not None:
            # White snail hunts Black king
            w_snail_pos = game_mode.white_snail.current_pos
            dist_b = max(abs(chess.square_file(b_king_sq) - w_snail_pos[0]),
                         abs(chess.square_rank(b_king_sq) - w_snail_pos[1]))
            if dist_b <= 1:
                black_pst -= 3000
            elif dist_b == 2:
                black_pst -= 400

    total_eval = (white_material - black_material) + (white_pst - black_pst)
    return total_eval


def score_move_mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """
    Score a move for alpha-beta move ordering.
    Orders captures by MVV-LVA (Most Valuable Victim - Least Valuable Attacker),
    promotions, checks, and quiet moves.
    """
    score = 0
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        victim_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
        attacker_val = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100
        # High value captures searched first
        score += 10000 + (victim_val * 10 - attacker_val)

    if move.promotion:
        # Give massive priority to Queen promotions; underpromotions get lower priority
        if move.promotion == chess.QUEEN:
            score += 15000
        elif move.promotion == chess.KNIGHT and board.gives_check(move):
            score += 9000
        else:
            score += 4000

    if board.gives_check(move):
        score += 2500

    return score


def filter_promotion_moves(moves: List[chess.Move], board: chess.Board) -> List[chess.Move]:
    """
    Prune redundant underpromotions (Rook and Bishop).
    Keep Queen promotion always, and Knight promotion only if it delivers check.
    Prevents a 4x branching factor explosion on pawn promotions.
    """
    has_promo = any(m.promotion is not None for m in moves)
    if not has_promo:
        return moves

    filtered = []
    for m in moves:
        if m.promotion is not None:
            if m.promotion == chess.QUEEN:
                filtered.append(m)
            elif m.promotion == chess.KNIGHT and board.gives_check(m):
                filtered.append(m)
        else:
            filtered.append(m)
    return filtered if filtered else moves


def order_moves(board: chess.Board, moves: List[chess.Move], filter_underpromotions: bool = True) -> List[chess.Move]:
    """Sort legal moves by tactical priority to maximize alpha-beta pruning."""
    if filter_underpromotions:
        moves = filter_promotion_moves(moves, board)
    return sorted(moves, key=lambda m: score_move_mvv_lva(board, m), reverse=True)


# -----------------------------------------------------------------------------
# Search Algorithms: Minimax, Alpha-Beta & Quiescence Search
# -----------------------------------------------------------------------------

def quiescence_search(
    board: chess.Board,
    alpha: int,
    beta: int,
    color_mult: int,
    game_mode: Optional[Any] = None,
    max_depth: int = 2,
    deadline: float = float("inf"),
    stop_check: Optional[threading.Event] = None,
    nodes_budget: Optional[List[int]] = None,
) -> int:
    """
    Search capturing sequences and Queen promotions until quiet position is reached.
    Uses strict node & time budgets to prevent freeze on pawn promotion / open queen positions.
    """
    if stop_check and stop_check.is_set():
        return 0
    if time.time() > deadline:
        return 0
    if nodes_budget is not None:
        if nodes_budget[0] <= 0:
            return evaluate_board(board, game_mode) * color_mult
        nodes_budget[0] -= 1

    stand_pat = evaluate_board(board, game_mode) * color_mult
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if max_depth <= 0:
        return stand_pat

    # Explore captures in quiescence
    capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
    capture_moves = order_moves(board, capture_moves, filter_underpromotions=True)

    for move in capture_moves:
        board.push(move)
        score = -quiescence_search(
            board,
            -beta,
            -alpha,
            -color_mult,
            game_mode,
            max_depth=max_depth - 1,
            deadline=deadline,
            stop_check=stop_check,
            nodes_budget=nodes_budget,
        )
        board.pop()

        if (stop_check and stop_check.is_set()) or time.time() > deadline:
            return alpha

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def alpha_beta_search(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    color_mult: int,
    game_mode: Optional[Any] = None,
    use_quiescence: bool = True,
    stop_check: Optional[threading.Event] = None,
    deadline: float = float("inf"),
    nodes_budget: Optional[List[int]] = None,
) -> int:
    """
    Minimax search with Alpha-Beta pruning, move ordering, and deadline enforcement.
    """
    if stop_check and stop_check.is_set():
        return 0
    if time.time() > deadline:
        return 0
    if nodes_budget is not None:
        if nodes_budget[0] <= 0:
            return evaluate_board(board, game_mode) * color_mult
        nodes_budget[0] -= 1

    if depth == 0:
        if use_quiescence:
            return quiescence_search(
                board,
                alpha,
                beta,
                color_mult,
                game_mode,
                max_depth=2,
                deadline=deadline,
                stop_check=stop_check,
                nodes_budget=nodes_budget,
            )
        return evaluate_board(board, game_mode) * color_mult

    if board.is_game_over():
        if board.is_checkmate():
            return -30000 - depth  # Prefer faster checkmates
        return 0

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return 0

    ordered = order_moves(board, legal_moves, filter_underpromotions=True)

    for move in ordered:
        board.push(move)
        score = -alpha_beta_search(
            board,
            depth - 1,
            -beta,
            -alpha,
            -color_mult,
            game_mode,
            use_quiescence,
            stop_check,
            deadline,
            nodes_budget,
        )
        board.pop()

        if (stop_check and stop_check.is_set()) or time.time() > deadline:
            return alpha

        if score >= beta:
            return beta  # Beta cutoff / prune
        if score > alpha:
            alpha = score

    return alpha


# -----------------------------------------------------------------------------
# Bot Decision Engine
# -----------------------------------------------------------------------------

def select_best_move(
    board: chess.Board,
    difficulty: BotDifficulty,
    game_mode: Optional[Any] = None,
    stop_event: Optional[threading.Event] = None,
) -> Optional[chess.Move]:
    """
    Compute and select the best move according to the given difficulty level.
    Guarantees responsive timing with strict search deadlines and clean promotion handling.
    """
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    # Immediate tactical mate-in-1: execute instantly for all levels (except Novice blunder mode)
    if difficulty != BotDifficulty.NOVICE:
        for m in legal_moves:
            board.push(m)
            if board.is_checkmate():
                board.pop()
                return m
            board.pop()

    color_mult = 1 if board.turn == chess.WHITE else -1
    meta = BOT_DIFFICULTY_METADATA[difficulty]
    target_depth = meta["depth"]
    ordered_moves = order_moves(board, legal_moves, filter_underpromotions=True)
    if not ordered_moves:
        ordered_moves = legal_moves

    start_time = time.time()

    # 1. NOVICE (~800 Elo)
    if difficulty == BotDifficulty.NOVICE:
        captures = [m for m in legal_moves if board.is_capture(m)]
        checks = [m for m in legal_moves if board.gives_check(m)]
        promotions = [m for m in legal_moves if m.promotion == chess.QUEEN]
        tactics = captures + checks + promotions

        # With 70% probability play a tactical move (capture, check, or promotion), otherwise random
        if tactics and random.random() < 0.70:
            best_t = max(tactics, key=lambda m: score_move_mvv_lva(board, m))
            return best_t

        # Avoid obvious immediate checkmate
        filtered_moves = []
        for m in legal_moves:
            board.push(m)
            if board.is_checkmate():
                board.pop()
                continue
            board.pop()
            filtered_moves.append(m)

        pool = filtered_moves if filtered_moves else legal_moves
        # If any queen promotion is available, prefer it
        q_promos = [m for m in pool if m.promotion == chess.QUEEN]
        if q_promos:
            return random.choice(q_promos)
        safe_pool = [m for m in pool if m.promotion in (None, chess.QUEEN)]
        return random.choice(safe_pool if safe_pool else pool)

    # 2. CASUAL (~1200 Elo)
    if difficulty == BotDifficulty.CASUAL:
        deadline = start_time + 0.40
        best_score = -999999
        best_moves = []
        budget = [8000]

        # Prioritize immediate queen promotions if available
        q_promos = [m for m in ordered_moves if m.promotion == chess.QUEEN]
        if q_promos and random.random() < 0.90:
            return q_promos[0]

        for move in ordered_moves:
            if (stop_event and stop_event.is_set()) or time.time() > deadline:
                break

            board.push(move)
            score = -alpha_beta_search(
                board,
                depth=1,
                alpha=-999999,
                beta=999999,
                color_mult=-color_mult,
                game_mode=game_mode,
                use_quiescence=False,
                stop_check=stop_event,
                deadline=deadline,
                nodes_budget=budget,
            )
            board.pop()

            promo_bonus = 30 if move.promotion == chess.QUEEN else 0
            noisy_score = score + promo_bonus + random.randint(-15, 15)
            if noisy_score > best_score:
                best_score = noisy_score
                best_moves = [move]
            elif abs(noisy_score - best_score) <= 12:
                best_moves.append(move)

        return random.choice(best_moves) if best_moves else ordered_moves[0]

    # 3. INTERMEDIATE (~1600 Elo)
    if difficulty == BotDifficulty.INTERMEDIATE:
        deadline = start_time + 0.90
        best_score = -999999
        best_move = ordered_moves[0]
        alpha = -999999
        beta = 999999
        budget = [20000]

        for move in ordered_moves:
            if (stop_event and stop_event.is_set()) or time.time() > deadline:
                break

            board.push(move)
            score = -alpha_beta_search(
                board,
                depth=target_depth - 1,
                alpha=-beta,
                beta=-alpha,
                color_mult=-color_mult,
                game_mode=game_mode,
                use_quiescence=True,
                stop_check=stop_event,
                deadline=deadline,
                nodes_budget=budget,
            )
            board.pop()

            promo_bonus = 25 if move.promotion == chess.QUEEN else 0
            adj_score = score + promo_bonus
            if adj_score > best_score:
                best_score = adj_score
                best_move = move
                alpha = max(alpha, score)
                if score >= 25000:
                    break

        return best_move

    # 4. MASTER (~2000+ Elo)
    deadline = start_time + 1.40
    best_score = -999999
    best_move = ordered_moves[0]
    alpha = -999999
    beta = 999999
    budget = [35000]

    for move in ordered_moves:
        if (stop_event and stop_event.is_set()) or time.time() > deadline:
            break

        board.push(move)
        score = -alpha_beta_search(
            board,
            depth=target_depth - 1,
            alpha=-beta,
            beta=-alpha,
            color_mult=-color_mult,
            game_mode=game_mode,
            use_quiescence=True,
            stop_check=stop_event,
            deadline=deadline,
            nodes_budget=budget,
        )
        board.pop()

        promo_bonus = 25 if move.promotion == chess.QUEEN else 0
        adj_score = score + promo_bonus
        if adj_score > best_score:
            best_score = adj_score
            best_move = move
            alpha = max(alpha, score)
            if score >= 25000:
                break

    return best_move


# -----------------------------------------------------------------------------
# Asynchronous Background Chess Bot Controller
# -----------------------------------------------------------------------------

class ChessBotController:
    """
    Manages background thread execution, timing, and turn dispatching for AI bot.
    Ensures the Pygame main application remains completely fluid at 60 FPS.
    """

    def __init__(self, difficulty: BotDifficulty = BotDifficulty.CASUAL):
        self.difficulty: BotDifficulty = difficulty
        self.enabled: bool = True
        self.player_color: chess.Color = chess.WHITE
        self.bot_color: chess.Color = chess.BLACK

        # Async background state
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._chosen_move: Optional[chess.Move] = None
        self._is_thinking: bool = False
        self._think_start_time: float = 0.0
        self._target_delay: float = 0.6
        self._uno_draw_pending: bool = False
        self._uno_draw_timer: float = 0.0

    @property
    def is_thinking(self) -> bool:
        return self._is_thinking

    @property
    def current_metadata(self) -> Dict[str, Any]:
        return BOT_DIFFICULTY_METADATA[self.difficulty]

    def set_difficulty(self, difficulty: BotDifficulty) -> None:
        """Update bot difficulty level."""
        self.difficulty = difficulty

    def cycle_difficulty(self, direction: int = 1) -> BotDifficulty:
        """Cycle through the 4 difficulty levels."""
        levels = list(BotDifficulty)
        idx = (levels.index(self.difficulty) + direction) % len(levels)
        self.difficulty = levels[idx]
        return self.difficulty

    def set_player_color(self, color: chess.Color) -> None:
        """Set which color the human controls; bot takes the opposite."""
        self.player_color = color
        self.bot_color = chess.BLACK if color == chess.WHITE else chess.WHITE
        self.cancel_thinking()

    def swap_sides(self) -> chess.Color:
        """Swap human and bot colors."""
        new_color = chess.BLACK if self.player_color == chess.WHITE else chess.WHITE
        self.set_player_color(new_color)
        return new_color

    def toggle_enabled(self) -> bool:
        """Toggle between Singleplayer vs AI and 2-Player Local."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.cancel_thinking()
        return self.enabled

    def is_bot_turn(self, game_state: Any) -> bool:
        """Return True if it is currently the AI Bot's turn to act."""
        if not self.enabled or game_state.is_game_over():
            return False
        return game_state.turn == self.bot_color

    def cancel_thinking(self) -> None:
        """Safely terminate any ongoing background search."""
        self._stop_event.set()
        self._thread = None
        self._chosen_move = None
        self._is_thinking = False
        self._uno_draw_pending = False
        self._stop_event = threading.Event()

    def start_thinking(self, game_state: Any) -> None:
        """Launch background search thread with natural human pacing delay."""
        if self._is_thinking or not self.is_bot_turn(game_state):
            return

        self._chosen_move = None
        self._is_thinking = True
        self._think_start_time = time.time()
        self._stop_event = threading.Event()

        meta = self.current_metadata
        self._target_delay = random.uniform(meta["min_delay"], meta["max_delay"])

        # Clone board to avoid any race condition with main thread
        board_copy = game_state.board.copy()
        mode_copy = game_state.mode
        diff = self.difficulty
        stop_ev = self._stop_event

        def _worker():
            try:
                move = select_best_move(board_copy, diff, mode_copy, stop_ev)
                if not stop_ev.is_set():
                    self._chosen_move = move
            except Exception:
                if not stop_ev.is_set():
                    legal = list(board_copy.legal_moves)
                    self._chosen_move = random.choice(legal) if legal else None

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def update(self, dt: float, game_state: Any) -> Tuple[Optional[chess.Move], bool]:
        """
        Poll thinking state each frame.
        Returns:
            (move_to_execute, trigger_uno_draw)
        """
        if not self.enabled or game_state.is_game_over() or not self.is_bot_turn(game_state):
            if self._is_thinking:
                self.cancel_thinking()
            return None, False

        # Check Chess + UNO Awaiting Draw phase
        from uno_engine import ChessUnoMode, UnoTurnPhase
        if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase == UnoTurnPhase.AWAITING_DRAW:
            if not self._uno_draw_pending:
                self._uno_draw_pending = True
                self._uno_draw_timer = 0.5  # Brief pause before bot draws card
                return None, False
            else:
                self._uno_draw_timer -= dt
                if self._uno_draw_timer <= 0:
                    self._uno_draw_pending = False
                    return None, True  # Trigger UNO Draw!
                return None, False

        # In UNO mode, do not think until card is active
        if isinstance(game_state.mode, ChessUnoMode) and game_state.mode.phase != UnoTurnPhase.CARD_ACTIVE:
            return None, False

        # If not thinking yet, start thinking
        if not self._is_thinking:
            self.start_thinking(game_state)
            return None, False

        # Check if thought thread finished and minimum human-like delay has passed
        elapsed = time.time() - self._think_start_time
        if not self._thread.is_alive() and elapsed >= self._target_delay:
            move = self._chosen_move
            # Safety fallback: ensure a non-None move is returned so bot NEVER gets stuck
            if move is None and not game_state.is_game_over():
                all_legal = []
                for sq in chess.SQUARES:
                    all_legal.extend(game_state.get_legal_moves_from(sq))
                if all_legal:
                    promos = [m for m in all_legal if m.promotion == chess.QUEEN]
                    caps = [m for m in all_legal if game_state.board.is_capture(m)]
                    pool = promos or caps or all_legal
                    move = random.choice(pool)

            self._is_thinking = False
            self._thread = None
            self._chosen_move = None
            return move, False

        return None, False
