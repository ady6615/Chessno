# test_timer.py
"""Unit tests for the ChessTimer system and its integration with GameState."""

import unittest
import chess
from src2.timer import ChessTimer
from src2.game_engine import GameState


class TestChessTimer(unittest.TestCase):
    def test_default_initialization(self):
        timer = ChessTimer(time_limit_seconds=300)
        self.assertEqual(timer.time_limit_seconds, 300)
        self.assertEqual(timer.white_time, 300.0)
        self.assertEqual(timer.black_time, 300.0)
        self.assertFalse(timer.is_running)
        self.assertFalse(timer.started)
        self.assertEqual(timer.active_color, chess.WHITE)
        self.assertIsNone(timer.timeout_color)
        self.assertTrue(timer.has_timer)
        self.assertFalse(timer.is_game_over())

    def test_unlimited_timer(self):
        timer = ChessTimer(time_limit_seconds=None)
        self.assertIsNone(timer.time_limit_seconds)
        self.assertFalse(timer.has_timer)
        self.assertEqual(timer.get_time_preset_label(), "Unlimited")
        self.assertEqual(timer.format_time(0), "Unlimited")

        # Starting an unlimited timer does not start countdown
        timer.start(chess.WHITE)
        self.assertFalse(timer.is_running)
        flag = timer.update(10.0)
        self.assertIsNone(flag)
        self.assertFalse(timer.is_game_over())

    def test_cycle_presets(self):
        timer = ChessTimer(time_limit_seconds=None)  # Index 0: Unlimited
        self.assertEqual(timer.get_time_preset_label(), "Unlimited")

        timer.cycle_preset(1)  # Index 1: 1 min
        self.assertEqual(timer.time_limit_seconds, 60)
        self.assertEqual(timer.get_time_preset_label(), "1 min")

        timer.cycle_preset(1)  # Index 2: 3 min
        self.assertEqual(timer.time_limit_seconds, 180)
        self.assertEqual(timer.get_time_preset_label(), "3 min")

        timer.cycle_preset(-1)  # Back to 1 min
        self.assertEqual(timer.time_limit_seconds, 60)

    def test_adjust_custom_minutes(self):
        timer = ChessTimer(time_limit_seconds=300)  # 5 min
        timer.adjust_custom_minutes(2)  # 7 min = 420s
        self.assertEqual(timer.time_limit_seconds, 420)
        self.assertEqual(timer.get_time_preset_label(), "7 min")
        self.assertEqual(timer.white_time, 420.0)
        self.assertEqual(timer.black_time, 420.0)

        # Clamping to bounds (1 min minimum, 60 min maximum)
        timer.adjust_custom_minutes(-100)
        self.assertEqual(timer.time_limit_seconds, 60)
        timer.adjust_custom_minutes(100)
        self.assertEqual(timer.time_limit_seconds, 3600)

    def test_countdown_and_turn_switching(self):
        timer = ChessTimer(time_limit_seconds=60)
        timer.start(chess.WHITE)
        self.assertTrue(timer.is_running)
        self.assertTrue(timer.started)
        self.assertEqual(timer.active_color, chess.WHITE)

        # Update white clock by 5 seconds
        flag = timer.update(5.0)
        self.assertIsNone(flag)
        self.assertAlmostEqual(timer.white_time, 55.0)
        self.assertAlmostEqual(timer.black_time, 60.0)

        # Switch to black
        timer.switch_turn(chess.BLACK)
        self.assertEqual(timer.active_color, chess.BLACK)

        # Update black clock by 10 seconds
        flag = timer.update(10.0)
        self.assertIsNone(flag)
        self.assertAlmostEqual(timer.white_time, 55.0)
        self.assertAlmostEqual(timer.black_time, 50.0)

    def test_pause_and_resume(self):
        timer = ChessTimer(time_limit_seconds=60)
        timer.start(chess.WHITE)
        timer.update(2.0)
        self.assertAlmostEqual(timer.white_time, 58.0)

        timer.pause()
        self.assertFalse(timer.is_running)

        # Clock should not decrease while paused
        timer.update(5.0)
        self.assertAlmostEqual(timer.white_time, 58.0)

        timer.resume()
        self.assertTrue(timer.is_running)
        timer.update(3.0)
        self.assertAlmostEqual(timer.white_time, 55.0)

    def test_flag_fall_timeout(self):
        timer = ChessTimer(time_limit_seconds=5)
        timer.start(chess.WHITE)

        flag = timer.update(4.0)
        self.assertIsNone(flag)
        self.assertFalse(timer.is_game_over())

        flag = timer.update(2.0)  # Exceeds 5.0 seconds
        self.assertEqual(flag, chess.WHITE)
        self.assertTrue(timer.is_game_over())
        self.assertEqual(timer.timeout_color, chess.WHITE)
        self.assertFalse(timer.is_running)
        self.assertEqual(timer.white_time, 0.0)

        # Further updates should do nothing
        flag2 = timer.update(5.0)
        self.assertIsNone(flag2)

    def test_low_time_and_formatting(self):
        timer = ChessTimer(time_limit_seconds=120)
        self.assertEqual(timer.format_time(125), "02:05")
        self.assertFalse(timer.is_low_time(chess.WHITE, threshold=30.0))

        timer.white_time = 25.0
        self.assertTrue(timer.is_low_time(chess.WHITE, threshold=30.0))

        # Precision display when under 10s and started
        timer.started = True
        formatted_under_10 = timer.format_time(7.4)
        self.assertEqual(formatted_under_10, "00:07.4")

    def test_game_state_timeout_integration(self):
        game = GameState()
        self.assertFalse(game.is_game_over())
        self.assertIsNone(game.winner())
        self.assertIsNone(game.game_over_reason())

        # Simulate White timing out
        game.set_timeout(chess.WHITE)
        self.assertTrue(game.is_game_over())
        self.assertEqual(game.winner(), chess.BLACK)
        self.assertEqual(game.game_over_reason(), "Time Out! Black wins on time")

        # Resetting game clears timeout
        game.reset()
        self.assertFalse(game.is_game_over())
        self.assertIsNone(game.winner())
        self.assertIsNone(game.game_over_reason())


if __name__ == "__main__":
    unittest.main()
