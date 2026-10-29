# timer.py
"""
Chess Match Timer (Chess Clock) for Chessno.

Features:
- Standard chess clock mechanics for White and Black players.
- Pre-match time control configuration:
  Presets: Unlimited (None), 1 min (Bullet), 3 min (Blitz), 5 min (Blitz),
           10 min (Rapid), 15 min (Classical), 30 min (Classical), and Custom minute increments.
- Precision countdown tracking per active player's turn.
- Low-time visual alert thresholds (< 30 seconds and tenth-of-a-second precision under 10 seconds).
- Automatic flag-fall (timeout) detection and resolution.
- Pause and resume support (e.g. during modals and mode selection).
"""

from typing import Dict, List, Optional, Tuple
import chess


class ChessTimer:
    """Manages match clocks, presets, and active turn countdowns."""

    PRESETS: List[Tuple[str, Optional[int]]] = [
        ("Unlimited", None),
        ("1 min", 60),
        ("3 min", 180),
        ("5 min", 300),
        ("10 min", 600),
        ("15 min", 900),
        ("30 min", 1800),
    ]

    def __init__(self, time_limit_seconds: Optional[int] = 300):
        self.time_limit_seconds: Optional[int] = time_limit_seconds
        self.white_time: float = float(time_limit_seconds) if time_limit_seconds else 0.0
        self.black_time: float = float(time_limit_seconds) if time_limit_seconds else 0.0
        self.is_running: bool = False
        self.started: bool = False
        self.active_color: chess.Color = chess.WHITE
        self.timeout_color: Optional[chess.Color] = None
        self.low_time_warned: Dict[chess.Color, bool] = {chess.WHITE: False, chess.BLACK: False}

    # -------------------------------------------------------------------------
    # Pre-match Configuration
    # -------------------------------------------------------------------------

    def set_time_limit(self, seconds: Optional[int]) -> None:
        """Set the initial time limit before starting a match."""
        self.time_limit_seconds = seconds
        self.reset()

    def cycle_preset(self, direction: int = 1) -> None:
        """Cycle through standard timer presets (forward or backward)."""
        current_val = self.time_limit_seconds
        preset_values = [p[1] for p in self.PRESETS]
        try:
            curr_idx = preset_values.index(current_val)
        except ValueError:
            curr_idx = 3  # default to 5 min if custom
        next_idx = (curr_idx + direction) % len(preset_values)
        self.set_time_limit(preset_values[next_idx])

    def adjust_custom_minutes(self, delta_minutes: int) -> None:
        """Adjust current timer by +/- minutes, clamping between 1 and 60 minutes."""
        current_sec = self.time_limit_seconds if self.time_limit_seconds is not None else 300
        new_min = max(1, min(60, (current_sec // 60) + delta_minutes))
        self.set_time_limit(new_min * 60)

    def reset(self) -> None:
        """Reset clocks back to the configured starting time limit."""
        if self.time_limit_seconds is not None:
            self.white_time = float(self.time_limit_seconds)
            self.black_time = float(self.time_limit_seconds)
        else:
            self.white_time = 0.0
            self.black_time = 0.0
        self.is_running = False
        self.started = False
        self.active_color = chess.WHITE
        self.timeout_color = None
        self.low_time_warned = {chess.WHITE: False, chess.BLACK: False}

    # -------------------------------------------------------------------------
    # In-Match Clock Control
    # -------------------------------------------------------------------------

    def start(self, turn: chess.Color = chess.WHITE) -> None:
        """Start or unpause the clock for the given player."""
        if self.time_limit_seconds is None or self.timeout_color is not None:
            return
        self.active_color = turn
        self.started = True
        self.is_running = True

    def pause(self) -> None:
        """Pause clock countdown without losing current times."""
        self.is_running = False

    def resume(self) -> None:
        """Resume ticking if a match is actively in progress."""
        if self.time_limit_seconds is not None and self.started and self.timeout_color is None:
            self.is_running = True

    def switch_turn(self, new_turn: chess.Color) -> None:
        """Switch active countdown to the other player when a move is completed."""
        self.active_color = new_turn
        if self.time_limit_seconds is not None and not self.started:
            self.started = True
            self.is_running = True

    def update(self, delta_seconds: float) -> Optional[chess.Color]:
        """
        Advance the active player's clock by delta_seconds.
        Returns chess.Color if a timeout (flag fall) just occurred, otherwise None.
        """
        if (
            not self.is_running
            or self.time_limit_seconds is None
            or self.timeout_color is not None
            or delta_seconds <= 0
        ):
            return None

        if self.active_color == chess.WHITE:
            self.white_time = max(0.0, self.white_time - delta_seconds)
            if self.white_time <= 0.0:
                self.white_time = 0.0
                self.timeout_color = chess.WHITE
                self.is_running = False
                return chess.WHITE
        else:
            self.black_time = max(0.0, self.black_time - delta_seconds)
            if self.black_time <= 0.0:
                self.black_time = 0.0
                self.timeout_color = chess.BLACK
                self.is_running = False
                return chess.BLACK

        return None

    # -------------------------------------------------------------------------
    # Status & Formatting Queries
    # -------------------------------------------------------------------------

    @property
    def has_timer(self) -> bool:
        """True if a finite time limit is enabled."""
        return self.time_limit_seconds is not None

    def is_game_over(self) -> bool:
        """True if either player has lost on time."""
        return self.timeout_color is not None

    def get_remaining_time(self, color: chess.Color) -> float:
        """Return remaining seconds for the specified player."""
        return self.white_time if color == chess.WHITE else self.black_time

    def is_low_time(self, color: chess.Color, threshold: float = 30.0) -> bool:
        """True if the specified player has less than threshold seconds left."""
        if not self.has_timer:
            return False
        return self.get_remaining_time(color) <= threshold

    def format_time(self, seconds: float) -> str:
        """Format seconds into MM:SS or MM:SS.s when under 10 seconds."""
        if self.time_limit_seconds is None:
            return "Unlimited"
        total_sec = max(0.0, seconds)
        mins = int(total_sec // 60)
        secs = int(total_sec % 60)
        if total_sec < 10.0 and self.started:
            tenths = int((total_sec - int(total_sec)) * 10)
            return f"{mins:02d}:{secs:02d}.{tenths}"
        return f"{mins:02d}:{secs:02d}"

    def get_time_preset_label(self) -> str:
        """Return human-readable label for current time control setting."""
        if self.time_limit_seconds is None:
            return "Unlimited"
        for label, sec in self.PRESETS:
            if sec == self.time_limit_seconds:
                return label
        mins = self.time_limit_seconds // 60
        return f"{mins} min"
