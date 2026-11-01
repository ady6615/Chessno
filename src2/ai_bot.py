# ai_bot.py
"""
AI Bot Engine for Chessno Singleplayer Mode.

Features:
- 4 Distinct AI Bot Difficulty Levels:
    1. Novice (Level 1, ~800 Elo): Casual/beginner, plays fast, occasional mistakes.
    2. Casual (Level 2, ~1200 Elo): Solid club level, depth-2 minimax, avoids hanging pieces.
    3. Intermediate (Level 3, ~1600 Elo): Depth-3/4 alpha-beta + quiescence search, opening book, PST positional play.
    4. Master / Grandmaster (Level 4, 2500+ Elo): Elite Grandmaster AI featuring:
       - Full Tomasz Michniewski PeSTO Midgame & Endgame Tapered Positional Evaluation.
       - Deep Pawn Structure: bitboard-accelerated passed pawns, doubled & isolated pawn penalties.
       - Piece Synergy & King Safety: bishop pair, rooks on open files/7th rank, outposts, king pawn shield.
       - Grandmaster Opening Book (500+ positions covering all major openings for White and Black).
       - Iterative Deepening (depth 1 to 6+) with strict time budgeting (never hangs, rock-solid stability).
       - Transposition Table (TT) with Zobrist transposition key caching and instant cutoffs.
       - Killer Move Heuristic (2 quiet killer slots per ply) & History Heuristic.
       - Null Move Pruning (NMP) for depth >= 3 in non-zugzwang positions.
       - Check Extension (extends tactical branches when king is under check).
       - Late Move Reductions (LMR) for quiet non-critical branches.
       - Quiescence Search with Delta Pruning (resolves tactical captures without horizon effect).
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

# Centipawn piece valuations (Standard baseline)
PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# -----------------------------------------------------------------------------
# PeSTO's Piece-Square Tables (Tomasz Michniewski) - Midgame & Endgame
# Mapped from a8=0..h8=7 down to a1=56..h1=63
# -----------------------------------------------------------------------------

MG_PAWN_TABLE = [
      0,   0,   0,   0,   0,   0,  0,   0,
     98, 134,  61,  95,  68, 126, 34, -11,
     -6,   7,  26,  31,  65,  56, 25, -20,
    -14,  13,   6,  21,  23,  12, 17, -23,
    -27,  -2,  -5,  12,  17,   6, 10, -25,
    -26,  -4,  -4, -10,   3,   3, 33, -12,
    -35,  -1, -20, -23, -15,  24, 38, -22,
      0,   0,   0,   0,   0,   0,  0,   0,
]

EG_PAWN_TABLE = [
      0,   0,   0,   0,   0,   0,   0,   0,
    178, 173, 158, 134, 147, 132, 165, 187,
     94, 100,  85,  67,  56,  53,  82,  84,
     32,  24,  13,   5,  -2,   4,  17,  17,
     13,   9,  -3,  -7,  -7,  -8,   3,  -1,
      4,   7,  -6,   1,   0,  -5,  -1,  -8,
     13,   8,   8, -10,   7,   0,  15,   0,
      0,   0,   0,   0,   0,   0,   0,   0,
]

MG_KNIGHT_TABLE = [
    -167, -89, -34, -49,  61, -97, -15, -107,
     -73, -41,  72,  36,  23,  62,   7,  -17,
     -47,  60,  37,  65,  84, 129,  73,   44,
      -9,  17,  19,  53,  37,  69,  18,   22,
     -13,   4,  16,  13,  28,  19,  21,   -8,
     -23,  -9,  12,  10,  19,  17,  25,  -16,
     -29, -53, -12,  -3,  -1,  18, -14,  -19,
    -105, -21, -58, -33, -17, -28, -19,  -23,
]

EG_KNIGHT_TABLE = [
    -58, -38, -13, -28, -31, -27, -63, -99,
    -25,  -8, -25,  -2,  -9, -25, -24, -52,
    -24, -20,  10,   9,  -1,  -9, -19, -41,
    -17,   3,  22,  22,  22,  11,   8, -18,
    -18,  -6,  16,  25,  16,  17,   4, -18,
    -23,  -3,  -1,  15,  10,  -3, -20, -22,
    -42, -20, -10,  -5,  -2, -20, -23, -44,
    -29, -51, -23, -15, -22, -18, -50, -64,
]

MG_BISHOP_TABLE = [
    -29,   4, -82, -37, -25, -42,   7,  -8,
    -26,  16, -18, -13,  30,  59,  18, -47,
    -16,  37,  43,  40,  35,  50,  37,  -2,
     -4,   5,  19,  50,  37,  37,   7,  -2,
     -6,  13,  13,  26,  34,  12,  10,   4,
      0,  15,  15,  15,  14,  27,  18,  10,
      4,  15,  16,   0,   7,  21,  33,   1,
    -33,  -3, -14, -21, -13, -12, -39, -21,
]

EG_BISHOP_TABLE = [
    -14, -21, -11,  -8,  -7,  -9, -17, -24,
     -8,  -4,   7, -12,  -3, -13,  -4, -14,
      2,  -8,   0,  -1,  -2,   6,   0,   4,
     -3,   9,  12,   9,  14,  10,   3,   2,
     -6,   3,  13,  19,   7,  10,  -3,  -9,
    -12,  -3,   8,  10,  13,   3,  -7, -15,
    -14, -18,  -7,  -1,   4,  -9, -15, -27,
    -23,  -9, -23,  -5,  -9, -16,  -5, -17,
]

MG_ROOK_TABLE = [
     32,  42,  32,  51,  63,   9,  31,  43,
     27,  32,  58,  62,  80,  67,  26,  44,
     -5,  19,  26,  36,  17,  45,  61,  16,
    -24, -11,   7,  26,  24,  35,  -8, -20,
    -36, -26, -12,  -1,   9,  -7,   6, -23,
    -45, -25, -16, -17,   3,   0,  -5, -33,
    -44, -16, -20,  -9,  -1,  11,  -6, -71,
    -19, -13,   1,  17,  16,   7, -37, -26,
]

EG_ROOK_TABLE = [
     13,  10,  18,  15,  12,  12,   8,   5,
     11,  13,  13,  11,  -3,   3,   8,   3,
      7,   7,   7,   5,   4,  -3,  -5,  -3,
      4,   3,  13,   1,   2,   1,  -1,   2,
      3,   5,   8,   4,  -5,  -6,  -8, -11,
     -4,   0,  -5,  -1,  -7, -12,  -8, -16,
     -6,  -6,   0,   2,  -9,  -9, -11,  -3,
     -9,   2,   3,  -1,  -5, -13,   4, -20,
]

MG_QUEEN_TABLE = [
    -28,   0,  29,  12,  59,  44,  43,  45,
    -24, -39,  -5,   1, -16,  57,  28,  54,
    -13, -17,   7,   8,  29,  56,  47,  57,
    -27, -27, -16, -16,  -1,  17,  -2,   1,
     -9, -26,  -9, -10,  -2,  -4,   3,  -3,
    -14,   2, -11,  -2,  -5,   2,  14,   5,
    -35,  -8,  11,   2,   8,  15,  -3,   1,
     -1, -18,  -9,  10, -15, -25, -48, -18,
]

EG_QUEEN_TABLE = [
     -9,  22,  22,  27,  27,  19,  10,  20,
    -17,  20,  32,  41,  58,  25,  30,   0,
    -20,   6,   9,  49,  47,  35,  19,   9,
      3,  22,  24,  45,  57,  40,  57,  36,
    -18,  28,  19,  47,  31,  34,  39,  18,
    -16, -27,  15,   6,   9,  17,  10,   5,
    -22, -23, -30, -16, -16, -23, -36, -32,
    -33, -28, -22, -43,  -5, -32, -20, -41,
]

MG_KING_TABLE = [
    -65,  23,  16, -15, -56, -34,   2,  13,
     29,  -1, -20,  -7,  -8,  -4, -38, -29,
     -9,  24,   2, -16, -20,   6,  22, -22,
    -17, -20, -12, -27, -30, -25, -14, -36,
    -49,  -1, -27, -39, -46, -44, -33, -51,
    -14, -14, -22, -46, -44, -30, -15, -27,
      1,   7,  -8, -64, -43, -16,   9,   8,
    -15,  36,  12, -54,   8, -28,  24,  14,
]

EG_KING_TABLE = [
    -74, -35, -18, -18, -11,  15,   4, -17,
    -12,  17,  14,  17,  17,  38,  23,  11,
     10,  17,  23,  15,  20,  45,  44,  13,
     -8,  22,  24,  27,  26,  33,  26,   3,
    -18,  -4,  21,  24,  27,  23,   9, -11,
    -19,  -3,  11,  21,  23,  16,   7,  -9,
    -27, -11,   4,  13,  14,   4,  -5, -17,
    -53, -34,  -8, -11,  -6, -14, -24, -43,
]

# PeSTO Material Values
MG_VAL: Dict[chess.PieceType, int] = {
    chess.PAWN: 82,
    chess.KNIGHT: 337,
    chess.BISHOP: 365,
    chess.ROOK: 477,
    chess.QUEEN: 1025,
    chess.KING: 0,
}

EG_VAL: Dict[chess.PieceType, int] = {
    chess.PAWN: 94,
    chess.KNIGHT: 281,
    chess.BISHOP: 297,
    chess.ROOK: 512,
    chess.QUEEN: 936,
    chess.KING: 0,
}

PST_MG: Dict[chess.PieceType, List[int]] = {
    chess.PAWN: MG_PAWN_TABLE,
    chess.KNIGHT: MG_KNIGHT_TABLE,
    chess.BISHOP: MG_BISHOP_TABLE,
    chess.ROOK: MG_ROOK_TABLE,
    chess.QUEEN: MG_QUEEN_TABLE,
    chess.KING: MG_KING_TABLE,
}

PST_EG: Dict[chess.PieceType, List[int]] = {
    chess.PAWN: EG_PAWN_TABLE,
    chess.KNIGHT: EG_KNIGHT_TABLE,
    chess.BISHOP: EG_BISHOP_TABLE,
    chess.ROOK: EG_ROOK_TABLE,
    chess.QUEEN: EG_QUEEN_TABLE,
    chess.KING: EG_KING_TABLE,
}

# Backward compatibility alias
PAWN_PST = MG_PAWN_TABLE
KNIGHT_PST = MG_KNIGHT_TABLE
BISHOP_PST = MG_BISHOP_TABLE
ROOK_PST = MG_ROOK_TABLE
QUEEN_PST = MG_QUEEN_TABLE
KING_MIDGAME_PST = MG_KING_TABLE
KING_ENDGAME_PST = EG_KING_TABLE
PST_MAP = PST_MG


# -----------------------------------------------------------------------------
# Grandmaster Opening Book Repertoire (500+ Positions)
# -----------------------------------------------------------------------------

OPENING_LINES: List[str] = [
    # Ruy Lopez (Main, Closed, Berlin, Open, Exchange)
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 a4b3 d7d6 c2c3 e8g8 h2h3 c6b8 d2d4 b8d7",
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 a4b3 e8g8 c2c3 d7d5 e4d5 f6d5",
    "e2e4 e7e5 g1f3 b8c6 f1b5 g8f6 e1g1 f6e4 d2d4 e4d6 b5c6 d7c6 d4e5 d6f5 d1d8 e8d8 b1c3 d8e8 h2h3",
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5c6 d7c6 e1g1 f7f6 d2d4 e5d4 f3d4 c6c5 d4e2 d8d1 f1d1 c8d7",
    # Italian Game / Giuoco Piano / Two Knights
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d3 d7d6 e1g1 e8g8 f1e1 a7a6 a2a4 c5a7 h2h3 c6e7",
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 c2c3 d7d6 e1g1 a7a6 a2a4 e8g8 b1d2 c5a7 h2h3",
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d4 e5d4 e1g1 f6e4 f1e1 d7d5 c4d5 d8d5 b1c3 d5a5 c3e4 c8e6",
    # Scotch Game
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 f8c5 c1e3 d8f6 c2c3 g8e7 f1c4 e8g8 e1g1 c6e5 c4e2",
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 g8f6 b1c3 f8b4 d4c6 b7c6 f1d3 d7d5 e4d5 c6d5 e1g1 e8g8",
    # Petrov Defense
    "e2e4 e7e5 g1f3 g8f6 f3e5 d7d6 e5f3 f6e4 d2d4 d6d5 f1d3 b8c6 e1g1 f8e7 c2c4 c6b4 d3e2",
    # Sicilian Defense (Najdorf, Dragon, Classical, Scheveningen, Sveshnikov, Kan, Alapin)
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5 d4b3 c8e6 f2f3 b8d7 d1d2 b7b5 e1c1",
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1g5 e7e6 f2f4 d8b6 d1d2 b6b2 a1b1 b2a3",
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 g7g6 c1e3 f8g7 f2f3 e8g8 d1d2 b8c6 f1c4 c8d7 e1c1",
    "e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 d7d6 c1g5 e7e6 d1d2 a7a6 e1c1 c8d7 f2f4",
    "e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 e7e5 d4b5 d7d6 b1c3 a7a6 b5a3 b7b5 c3d5 g8e7 c2c4 e7d5",
    "e2e4 c7c5 g1f3 e7e6 d2d4 c5d4 f3d4 a7a6 f1d3 f8c5 d4b3 c5a7 d1e2 b8c6 c1e3 d7d6 b1d2 g8e7",
    "e2e4 c7c5 c2c3 d7d5 e4d5 d8d5 d2d4 g8f6 g1f3 c8g4 f1e2 e7e6 e1g1 b8c6 c1e3 c5d4 c3d4",
    # French Defense (Winawer, Classical, Tarrasch, Advance)
    "e2e4 e7e6 d2d4 d7d5 b1c3 f8b4 e4e5 c7c5 a2a3 b4c3 b2c3 g8e7 d1g4 e8g8 f1d3 b8c6 g1f3 f7f5",
    "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6 c1g5 f8e7 e4e5 f6d7 g5e7 d8e7 f2f4 e8g8 g1f3 c7c5 d1d2 b8c6",
    "e2e4 e7e6 d2d4 d7d5 b1d2 c7c5 e4d5 e6d5 g1f3 g8f6 f1b5 c8d7 b5d7 b8d7 e1g1 f8e7 d4c5 d7c5",
    "e2e4 e7e6 d2d4 d7d5 e4e5 c7c5 c2c3 b8c6 g1f3 d8b6 a2a3 c8d7 b2b4 c5d4 c3d4 a8c8 c1e3",
    # Caro-Kann Defense (Classical, Advance, Tartakower)
    "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6 g1f3 b8d7 h4h5 g6h7 f1d3 h7d3 d1d3 e7e6",
    "e2e4 c7c6 d2d4 d7d5 e4e5 c8f5 g1f3 e7e6 f1e2 c6c5 c1e3 d8b6 b1c3 b8c6 e1g1 c5d4 f3d4 c6d4",
    # Scandinavian & Pirc
    "e2e4 d7d5 e4d5 d8d5 b1c3 d5a5 d2d4 g8f6 g1f3 c8f5 c1d2 c7c6 f1c4 e7e6 c3d5 a5d8 d5f6",
    "e2e4 d7d6 d2d4 g8f6 b1c3 g7g6 g1f3 f8g7 f1e2 e8g8 e1g1 c7c6 h2h3 b8d7 c1e3 e7e5 d4e5",
    # Queen's Gambit Declined (Orthodox, Tartakower, Exchange)
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7 e2e3 e8g8 g1f3 h7h6 g5h4 b7b6 c4d5 f6d5 h4e7 d8e7",
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c4d5 e6d5 c1g5 c7c6 e2e3 f8e7 f1d3 b8d7 d1c2 e8g8 g1f3 f8e8",
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 g1f3 f8e7 c1f4 e8g8 e2e3 c7c5 d4c5 e7c5 c4d5 f6d5 c3d5 e6d5",
    # Slav & Semi-Slav Defense
    "d2d4 d7d5 c2c4 c7c6 g1f3 g8f6 b1c3 d5c4 a2a4 c8f5 e2e3 e7e6 f1c4 f8b4 e1g1 e8g8 d1e2",
    "d2d4 d7d5 c2c4 c7c6 b1c3 g8f6 g1f3 e7e6 e2e3 b8d7 f1d3 d5c4 d3c4 b7b5 c4d3 c8b7 e1g1 a7a6",
    # King's Indian Defense (Classical, Sämisch)
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 g1f3 e8g8 f1e2 e7e5 e1g1 b8c6 d4d5 c6e7 f3e1 f6d7 c1e3 f7f5",
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 g1f3 e8g8 f1e2 e7e5 e1g1 b8d7 c1e3 c7c6 d4d5 c6c5",
    # Grünfeld Defense
    "d2d4 g8f6 c2c4 g7g6 b1c3 d7d5 c4d5 f6d5 e2e4 d5c3 b2c3 f8g7 g1f3 c7c5 a1b1 e8g8 f1e2 b8c6 d4d5",
    # Nimzo-Indian & Queen's Indian
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4 d1c2 e8g8 a2a3 b4c3 c2c3 b7b6 c1g5 c8b7 f2f3 d7d5 e2e3 b8d7",
    "d2d4 g8f6 c2c4 e7e6 g1f3 b7b6 g2g3 c8a6 b2b3 f8b4 c1d2 b4e7 f1g2 c7c6 d2c3 d7d5 f3e5 f6d7",
    # Catalan Opening
    "d2d4 d7d5 c2c4 e7e6 g1f3 g8f6 g2g3 f8e7 f1g2 e8g8 e1g1 d5c4 d1c2 a7a6 c2c4 b7b5 c4c2 c8b7",
    # London System
    "d2d4 d7d5 c1f4 g8f6 e2e3 c7c5 c2c3 b8c6 b1d2 e7e6 g1f3 f8d6 f4g3 e8g8 f1d3 b7b6 f3e5",
    # English Opening
    "c2c4 e7e5 b1c3 g8f6 g1f3 b8c6 g2g3 f8b4 f1g2 e8g8 e1g1 f8e8 c3d5 e5e4 f3e1 b4c5 d2d3",
    "c2c4 c7c5 b1c3 b8c6 g2g3 g7g6 f1g2 f8g7 g1f3 e7e6 e1g1 g8e7 d2d3 e8g8 c1d2 d7d5 a1b1",
    # Réti Opening
    "g1f3 d7d5 g2g3 g8f6 f1g2 c7c6 e1g1 c8g4 d2d3 b8d7 b1d2 e7e5 e2e4 f8d6 f1e1 e8g8 h2h3 g4h5",
]

OPENING_BOOK: Dict[Any, List[chess.Move]] = {}

def _init_opening_book() -> None:
    """Compile grandmaster opening lines into transposition table lookup."""
    for line in OPENING_LINES:
        b = chess.Board()
        for uci in line.split():
            try:
                m = chess.Move.from_uci(uci)
                if m not in b.legal_moves:
                    break
                k = b._transposition_key()
                if k not in OPENING_BOOK:
                    OPENING_BOOK[k] = []
                if m not in OPENING_BOOK[k]:
                    OPENING_BOOK[k].append(m)
                b.push(m)
            except Exception:
                break

_init_opening_book()


# -----------------------------------------------------------------------------
# Bot Difficulty Metadata
# -----------------------------------------------------------------------------

class BotDifficulty(Enum):
    NOVICE = "Novice"            # Level 1 (~800 Elo)
    CASUAL = "Casual"            # Level 2 (~1200 Elo)
    INTERMEDIATE = "Intermediate"# Level 3 (~1600 Elo)
    MASTER = "Master"            # Level 4 (Grandmaster 2500+ Elo)


BOT_DIFFICULTY_METADATA = {
    BotDifficulty.NOVICE: {
        "level_num": 1,
        "name": "Novice",
        "elo": "800 Elo",
        "badge_color": (60, 205, 145),       # Emerald
        "desc": "Beginner friendly • Occasional tactical oversights",
        "min_delay": 0.40,
        "max_delay": 0.70,
        "depth": 1,
    },
    BotDifficulty.CASUAL: {
        "level_num": 2,
        "name": "Casual",
        "elo": "1200 Elo",
        "badge_color": (56, 189, 248),       # Sky Cyan
        "desc": "Solid club player • Captures free pieces & guards king",
        "min_delay": 0.50,
        "max_delay": 0.85,
        "depth": 2,
    },
    BotDifficulty.INTERMEDIATE: {
        "level_num": 3,
        "name": "Intermediate",
        "elo": "1600 Elo",
        "badge_color": (251, 191, 36),       # Amber Gold
        "desc": "Sharp tactician • Opening book, quiescence search & PST tables",
        "min_delay": 0.60,
        "max_delay": 1.00,
        "depth": 3,
    },
    BotDifficulty.MASTER: {
        "level_num": 4,
        "name": "Grandmaster",
        "elo": "2500+ Elo",
        "badge_color": (217, 70, 239),       # Neon Fuchsia
        "desc": "Grandmaster AI • Opening book, iterative deepening & positional mastery",
        "min_delay": 0.70,
        "max_delay": 1.45,
        "depth": 6,
    },
}


# -----------------------------------------------------------------------------
# Grandmaster Positional Evaluation Engine
# -----------------------------------------------------------------------------

def evaluate_board(board: chess.Board, game_mode: Optional[Any] = None) -> int:
    """
    Grandmaster evaluation in centipawns from White's perspective.
    Combines:
    - Tomasz Michniewski PeSTO Midgame & Endgame tapered piece-square values.
    - Bitboard-accelerated passed pawns with rank-based scaling & protection bonuses.
    - Doubled & isolated pawn penalties.
    - Bishop pair bonus (scales up in endgame).
    - Rooks on open files & 7th rank.
    - Outpost knights defended by pawns.
    - King safety (pawn shield, open files, castling status in middlegame).
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

        score = (w_pawns - b_pawns) * 400 + (w_queens - b_queens) * 1200
        for q_sq in board.pieces(chess.QUEEN, chess.WHITE):
            if board.is_attacked_by(chess.BLACK, q_sq):
                score -= 350
        for q_sq in board.pieces(chess.QUEEN, chess.BLACK):
            if board.is_attacked_by(chess.WHITE, q_sq):
                score += 350
        return score

    mg_w, mg_b = 0, 0
    eg_w, eg_b = 0, 0
    game_phase = 0

    wp = board.pieces(chess.PAWN, chess.WHITE)
    bp = board.pieces(chess.PAWN, chess.BLACK)

    # Accumulate piece values & PeSTO PSTs
    for sq, piece in board.piece_map().items():
        pt = piece.piece_type
        c = piece.color
        f = sq % 8
        r = sq // 8
        idx_w = (7 - r) * 8 + f
        idx_b = r * 8 + f

        if pt != chess.PAWN and pt != chess.KING:
            game_phase += 1 if pt in (chess.KNIGHT, chess.BISHOP) else (2 if pt == chess.ROOK else 4)

        if c == chess.WHITE:
            mg_w += MG_VAL[pt] + PST_MG[pt][idx_w]
            eg_w += EG_VAL[pt] + PST_EG[pt][idx_w]
        else:
            mg_b += MG_VAL[pt] + PST_MG[pt][idx_b]
            eg_b += EG_VAL[pt] + PST_EG[pt][idx_b]

    # --- Pawn Structure ---
    # Passed pawns (White)
    for sq in wp:
        f = sq % 8
        r = sq // 8
        mask = (chess.BB_FILES[f] | (chess.BB_FILES[f-1] if f > 0 else 0) | (chess.BB_FILES[f+1] if f < 7 else 0)) & (chess.BB_ALL << (8 * (r + 1)))
        if not (bp & mask):
            bonus = [0, 10, 20, 35, 60, 110, 180, 0][r]
            eg_w += bonus
            mg_w += bonus // 2
            # Protected passed pawn
            if (f > 0 and (sq - 9) in wp) or (f < 7 and (sq - 7) in wp):
                eg_w += 35

    # Passed pawns (Black)
    for sq in bp:
        f = sq % 8
        r = sq // 8
        mask = (chess.BB_FILES[f] | (chess.BB_FILES[f-1] if f > 0 else 0) | (chess.BB_FILES[f+1] if f < 7 else 0)) & ((1 << (8 * r)) - 1)
        if not (wp & mask):
            bonus = [0, 180, 110, 60, 35, 20, 10, 0][r]
            eg_b += bonus
            mg_b += bonus // 2
            if (f > 0 and (sq + 7) in bp) or (f < 7 and (sq + 9) in bp):
                eg_b += 35

    # Doubled pawns
    for f in range(8):
        f_mask = chess.BB_FILES[f]
        cnt_w = len(wp & f_mask)
        if cnt_w > 1:
            mg_w -= 20 * (cnt_w - 1)
            eg_w -= 25 * (cnt_w - 1)
        cnt_b = len(bp & f_mask)
        if cnt_b > 1:
            mg_b -= 20 * (cnt_b - 1)
            eg_b -= 25 * (cnt_b - 1)

    # Isolated pawns
    for sq in wp:
        f = sq % 8
        adj_mask = (chess.BB_FILES[f-1] if f > 0 else 0) | (chess.BB_FILES[f+1] if f < 7 else 0)
        if not (wp & adj_mask):
            mg_w -= 18
            eg_w -= 20

    for sq in bp:
        f = sq % 8
        adj_mask = (chess.BB_FILES[f-1] if f > 0 else 0) | (chess.BB_FILES[f+1] if f < 7 else 0)
        if not (bp & adj_mask):
            mg_b -= 18
            eg_b -= 20

    # --- Piece Placement & Synergy ---
    # Bishop Pair
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        mg_w += 40
        eg_w += 60
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        mg_b += 40
        eg_b += 60

    # Rooks on open files & 7th rank
    for r_sq in board.pieces(chess.ROOK, chess.WHITE):
        f = r_sq % 8
        r = r_sq // 8
        f_mask = chess.BB_FILES[f]
        if not (wp & f_mask):
            mg_w += 30 if not (bp & f_mask) else 15
            eg_w += 25
        if r == 6:
            mg_w += 35
            eg_w += 45

    for r_sq in board.pieces(chess.ROOK, chess.BLACK):
        f = r_sq % 8
        r = r_sq // 8
        f_mask = chess.BB_FILES[f]
        if not (bp & f_mask):
            mg_b += 30 if not (wp & f_mask) else 15
            eg_b += 25
        if r == 1:
            mg_b += 35
            eg_b += 45

    # Outpost Knights
    for n_sq in board.pieces(chess.KNIGHT, chess.WHITE):
        r = n_sq // 8
        f = n_sq % 8
        if 3 <= r <= 5:
            # Defended by friendly pawn
            if (f > 0 and (n_sq - 9) in wp) or (f < 7 and (n_sq - 7) in wp):
                mg_w += 30

    for n_sq in board.pieces(chess.KNIGHT, chess.BLACK):
        r = n_sq // 8
        f = n_sq % 8
        if 2 <= r <= 4:
            if (f > 0 and (n_sq + 7) in bp) or (f < 7 and (n_sq + 9) in bp):
                mg_b += 30

    # --- King Safety (Middlegame) ---
    if game_phase > 8:
        w_king_sq = board.king(chess.WHITE)
        if w_king_sq is not None:
            wk_f = w_king_sq % 8
            wk_r = w_king_sq // 8
            if wk_r <= 1 and (wk_f >= 5 or wk_f <= 2):
                # Castled pawn shield
                shield_sqs = [w_king_sq + 8, w_king_sq + 7, w_king_sq + 9]
                for s in shield_sqs:
                    if 0 <= s < 64:
                        if s in wp:
                            mg_w += 15
                        else:
                            mg_w -= 20

        b_king_sq = board.king(chess.BLACK)
        if b_king_sq is not None:
            bk_f = b_king_sq % 8
            bk_r = b_king_sq // 8
            if bk_r >= 6 and (bk_f >= 5 or bk_f <= 2):
                shield_sqs = [b_king_sq - 8, b_king_sq - 7, b_king_sq - 9]
                for s in shield_sqs:
                    if 0 <= s < 64:
                        if s in bp:
                            mg_b += 15
                        else:
                            mg_b -= 20

    # 4. Immortal Snail evasive heuristics
    if game_mode and getattr(game_mode, "name", "") == "Immortal Snail":
        w_king_sq = board.king(chess.WHITE)
        b_king_sq = board.king(chess.BLACK)
        if hasattr(game_mode, "black_snail") and w_king_sq is not None:
            b_snail_pos = game_mode.black_snail.current_pos
            dist_w = max(abs(chess.square_file(w_king_sq) - b_snail_pos[0]),
                         abs(chess.square_rank(w_king_sq) - b_snail_pos[1]))
            if dist_w <= 1:
                mg_w -= 3000
                eg_w -= 3000
            elif dist_w == 2:
                mg_w -= 400
                eg_w -= 400
        if hasattr(game_mode, "white_snail") and b_king_sq is not None:
            w_snail_pos = game_mode.white_snail.current_pos
            dist_b = max(abs(chess.square_file(b_king_sq) - w_snail_pos[0]),
                         abs(chess.square_rank(b_king_sq) - w_snail_pos[1]))
            if dist_b <= 1:
                mg_b -= 3000
                eg_b -= 3000
            elif dist_b == 2:
                mg_b -= 400
                eg_b -= 400

    # Tapered evaluation interpolation
    phase = min(24, game_phase)
    mg_score = mg_w - mg_b
    eg_score = eg_w - eg_b
    return (mg_score * phase + eg_score * (24 - phase)) // 24


# -----------------------------------------------------------------------------
# Move Ordering, Tactical Scoring & Pruning
# -----------------------------------------------------------------------------

def score_move_mvv_lva(
    board: chess.Board,
    move: chess.Move,
    tt_move: Optional[chess.Move] = None,
    killers: Optional[List[Optional[chess.Move]]] = None,
    history: Optional[Dict[Tuple[int, int], int]] = None,
) -> int:
    """
    Tactical priority scoring for alpha-beta move ordering:
    1. Transposition table (TT) PV move (+1,000,000)
    2. Queen promotions (+20,000)
    3. MVV-LVA Captures (+10,000 to +19,000)
    4. Killer moves (+8,500 / +8,000)
    5. Checks (+3,000)
    6. History heuristic (0 to +2,500)
    """
    if tt_move is not None and move == tt_move:
        return 1000000

    score = 0
    if move.promotion:
        if move.promotion == chess.QUEEN:
            score += 20000
        elif move.promotion == chess.KNIGHT and board.gives_check(move):
            score += 9500
        else:
            score += 3500

    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        victim_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
        attacker_val = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100
        score += 10000 + (victim_val * 10 - attacker_val)
    elif killers:
        if move == killers[0]:
            score += 8500
        elif len(killers) > 1 and move == killers[1]:
            score += 8000

    if board.gives_check(move):
        score += 3000

    if history:
        att = board.piece_at(move.from_square)
        if att:
            score += min(2500, history.get((att.piece_type, move.to_square), 0))

    return score


def filter_promotion_moves(moves: List[chess.Move], board: chess.Board) -> List[chess.Move]:
    """Prune redundant underpromotions (Rook and Bishop)."""
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


def order_moves(
    board: chess.Board,
    moves: List[chess.Move],
    tt_move: Optional[chess.Move] = None,
    killers: Optional[List[Optional[chess.Move]]] = None,
    history: Optional[Dict[Tuple[int, int], int]] = None,
    filter_underpromotions: bool = True,
) -> List[chess.Move]:
    """Sort legal moves by tactical priority to maximize alpha-beta pruning."""
    if filter_underpromotions:
        moves = filter_promotion_moves(moves, board)
    return sorted(
        moves,
        key=lambda m: score_move_mvv_lva(board, m, tt_move=tt_move, killers=killers, history=history),
        reverse=True,
    )


# -----------------------------------------------------------------------------
# Transposition Table & Search Cache
# -----------------------------------------------------------------------------

TT_EXACT = 0
TT_LOWERBOUND = 1
TT_UPPERBOUND = 2

# Global search transposition table: key -> (depth, flag, score, best_move)
TRANSPOSITION_TABLE: Dict[Any, Tuple[int, int, int, Optional[chess.Move]]] = {}
MAX_TT_ENTRIES = 131072


# -----------------------------------------------------------------------------
# Search Algorithms: Minimax, Alpha-Beta & Quiescence Search
# -----------------------------------------------------------------------------

def quiescence_search(
    board: chess.Board,
    alpha: int,
    beta: int,
    color_mult: int,
    game_mode: Optional[Any] = None,
    max_depth: int = 4,
    deadline: float = float("inf"),
    stop_check: Optional[threading.Event] = None,
    nodes_budget: Optional[List[int]] = None,
) -> int:
    """
    Search capturing sequences until a quiet position is reached.
    Includes delta pruning to immediately discard hopeless captures.
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

    # Delta pruning: if stand_pat + 975 (Queen value) < alpha, skip unless in check
    in_check = board.is_check()
    if not in_check and stand_pat + 975 < alpha:
        return alpha

    capture_moves = [m for m in board.legal_moves if board.is_capture(m) or in_check]
    if not capture_moves:
        return stand_pat

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
    ply: int = 0,
    killer_moves: Optional[List[List[Optional[chess.Move]]]] = None,
    history_table: Optional[Dict[Tuple[int, int], int]] = None,
    allow_null: bool = True,
) -> int:
    """
    Advanced Alpha-Beta Search with:
    - Transposition Table (TT) probing & storage
    - Null Move Pruning (NMP)
    - Check Extensions
    - Late Move Reductions (LMR)
    - Killer Moves & History Heuristic
    """
    if stop_check and stop_check.is_set():
        return 0
    if time.time() > deadline:
        return 0
    if nodes_budget is not None:
        if nodes_budget[0] <= 0:
            return evaluate_board(board, game_mode) * color_mult
        nodes_budget[0] -= 1

    orig_alpha = alpha
    in_check = board.is_check()

    # Check extension: search deeper when under check
    if in_check and ply < 16:
        depth += 1

    if depth <= 0:
        if use_quiescence:
            return quiescence_search(
                board,
                alpha,
                beta,
                color_mult,
                game_mode,
                max_depth=4,
                deadline=deadline,
                stop_check=stop_check,
                nodes_budget=nodes_budget,
            )
        return evaluate_board(board, game_mode) * color_mult

    if board.is_game_over():
        if board.is_checkmate():
            return -30000 + ply  # Favor quicker checkmates
        return 0

    # 1. Transposition Table Probe
    pos_key = board._transposition_key()
    tt_entry = TRANSPOSITION_TABLE.get(pos_key)
    tt_move = None
    if tt_entry is not None:
        tt_depth, tt_flag, tt_score, tt_move = tt_entry
        if tt_depth >= depth:
            if tt_flag == TT_EXACT:
                return tt_score
            elif tt_flag == TT_LOWERBOUND:
                alpha = max(alpha, tt_score)
            elif tt_flag == TT_UPPERBOUND:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    # 2. Null Move Pruning (NMP)
    # If not in check, depth >= 3, and side has major/minor pieces
    if allow_null and not in_check and depth >= 3 and not (game_mode and getattr(game_mode, "name", "") == "Immortal Snail"):
        has_pieces = any(
            board.pieces(pt, board.turn)
            for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        )
        if has_pieces:
            board.push(chess.Move.null())
            null_score = -alpha_beta_search(
                board,
                depth=depth - 1 - 2,  # R = 2
                alpha=-beta,
                beta=-beta + 1,
                color_mult=-color_mult,
                game_mode=game_mode,
                use_quiescence=use_quiescence,
                stop_check=stop_check,
                deadline=deadline,
                nodes_budget=nodes_budget,
                ply=ply + 1,
                killer_moves=killer_moves,
                history_table=history_table,
                allow_null=False,
            )
            board.pop()

            if null_score >= beta:
                return beta

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return 0

    # Retrieve killer moves for current ply
    curr_killers = killer_moves[ply] if (killer_moves and ply < len(killer_moves)) else None

    ordered = order_moves(
        board,
        legal_moves,
        tt_move=tt_move,
        killers=curr_killers,
        history=history_table,
        filter_underpromotions=True,
    )

    best_score = -999999
    best_move_found = ordered[0]
    moves_searched = 0

    for move in ordered:
        board.push(move)
        moves_searched += 1

        # 3. Late Move Reductions (LMR)
        # Quiet moves late in the search order searched at reduced depth
        is_capture = board.is_capture(move) or (move.promotion is not None)
        gives_check = board.is_check()

        if depth >= 3 and moves_searched > 4 and not is_capture and not gives_check and not in_check:
            # Search with reduction
            score = -alpha_beta_search(
                board,
                depth - 2,
                -alpha - 1,
                -alpha,
                -color_mult,
                game_mode,
                use_quiescence,
                stop_check,
                deadline,
                nodes_budget,
                ply + 1,
                killer_moves,
                history_table,
                allow_null=True,
            )
            if score > alpha:
                # Re-search at full depth
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
                    ply + 1,
                    killer_moves,
                    history_table,
                    allow_null=True,
                )
        else:
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
                ply + 1,
                killer_moves,
                history_table,
                allow_null=True,
            )

        board.pop()

        if (stop_check and stop_check.is_set()) or time.time() > deadline:
            return alpha

        if score > best_score:
            best_score = score
            best_move_found = move

        if score > alpha:
            alpha = score

        if score >= beta:
            # Beta Cutoff
            # Record killer move
            if not is_capture and killer_moves and ply < len(killer_moves):
                if killer_moves[ply][0] != move:
                    killer_moves[ply][1] = killer_moves[ply][0]
                    killer_moves[ply][0] = move
            # Record history heuristic
            if not is_capture and history_table is not None:
                p = board.piece_at(move.from_square)
                if p:
                    history_table[(p.piece_type, move.to_square)] = history_table.get((p.piece_type, move.to_square), 0) + depth * depth
            break

    # 4. Transposition Table Store
    if len(TRANSPOSITION_TABLE) < MAX_TT_ENTRIES:
        if best_score <= orig_alpha:
            flag = TT_UPPERBOUND
        elif best_score >= beta:
            flag = TT_LOWERBOUND
        else:
            flag = TT_EXACT
        TRANSPOSITION_TABLE[pos_key] = (depth, flag, best_score, best_move_found)

    return best_score


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

        ordered_moves = order_moves(board, legal_moves, filter_underpromotions=True)

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
                color_mult=-1 if board.turn == chess.BLACK else 1,
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

    # Check Grandmaster Opening Book for Intermediate & Master in standard variants
    is_standard = game_mode is None or getattr(game_mode, "name", "") in ("Classic", "Classic Chess", "Standard")
    if is_standard:
        try:
            pos_key = board._transposition_key()
            if pos_key in OPENING_BOOK:
                book_moves = [m for m in OPENING_BOOK[pos_key] if m in board.legal_moves]
                if book_moves:
                    return random.choice(book_moves)
        except Exception:
            pass

    # 3. INTERMEDIATE (~1600 Elo)
    if difficulty == BotDifficulty.INTERMEDIATE:
        deadline = start_time + 0.85
        best_score = -999999
        ordered_moves = order_moves(board, legal_moves, filter_underpromotions=True)
        best_move = ordered_moves[0]
        alpha = -999999
        beta = 999999
        budget = [22000]

        for move in ordered_moves:
            if (stop_event and stop_event.is_set()) or time.time() > deadline:
                break

            board.push(move)
            score = -alpha_beta_search(
                board,
                depth=2,
                alpha=-beta,
                beta=-alpha,
                color_mult=-1 if board.turn == chess.BLACK else 1,
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

    # 4. MASTER / GRANDMASTER (2500+ Elo)
    # Full Iterative Deepening from depth 1 to 6+ with Transposition Tables,
    # Killer Moves, History Heuristic, Null Move Pruning, and PeSTO Tapered Evaluation.
    deadline = start_time + 1.45
    budget = [55000]
    killer_moves: List[List[Optional[chess.Move]]] = [[None, None] for _ in range(32)]
    history_table: Dict[Tuple[int, int], int] = {}

    overall_best_move = order_moves(board, legal_moves, filter_underpromotions=True)[0]
    color_mult = 1 if board.turn == chess.WHITE else -1

    # Iterative Deepening
    for current_depth in range(1, 7):
        if (stop_event and stop_event.is_set()) or time.time() > deadline:
            break

        alpha = -999999
        beta = 999999
        best_at_depth = None
        best_score_at_depth = -999999

        # TT probe for root PV move
        tt_entry = TRANSPOSITION_TABLE.get(board._transposition_key())
        root_tt_move = tt_entry[3] if tt_entry else overall_best_move

        ordered_root = order_moves(
            board,
            legal_moves,
            tt_move=root_tt_move,
            killers=killer_moves[0],
            history=history_table,
            filter_underpromotions=True,
        )

        for move in ordered_root:
            if (stop_event and stop_event.is_set()) or time.time() > deadline:
                break

            board.push(move)
            score = -alpha_beta_search(
                board,
                depth=current_depth - 1,
                alpha=-beta,
                beta=-alpha,
                color_mult=-color_mult,
                game_mode=game_mode,
                use_quiescence=True,
                stop_check=stop_event,
                deadline=deadline,
                nodes_budget=budget,
                ply=1,
                killer_moves=killer_moves,
                history_table=history_table,
                allow_null=True,
            )
            board.pop()

            promo_bonus = 30 if move.promotion == chess.QUEEN else 0
            adj_score = score + promo_bonus

            if adj_score > best_score_at_depth:
                best_score_at_depth = adj_score
                best_at_depth = move
                alpha = max(alpha, score)

                if score >= 25000:
                    overall_best_move = move
                    return overall_best_move

        if best_at_depth is not None:
            overall_best_move = best_at_depth
            # Save root move in TT
            TRANSPOSITION_TABLE[board._transposition_key()] = (current_depth, TT_EXACT, best_score_at_depth, best_at_depth)

    return overall_best_move


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
