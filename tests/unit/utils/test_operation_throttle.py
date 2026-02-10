from unittest.mock import patch

from fotura.utils.operation_throttle import OperationThrottle


class TestOperationThrottle:
    def test_allows_operations_within_limit(self):
        result = 0

        with patch("fotura.utils.operation_throttle.time") as mock_time:
            mock_time.monotonic.return_value = 0.0

            throttle = OperationThrottle(max_operations=5, window_seconds=1.0)
            for _ in range(5):
                with throttle:
                    result += 1

            assert result == 5
            mock_time.sleep.assert_not_called()

    def test_blocks_when_limit_exceeded(self):
        current_time = [0.0]

        def advance_time(seconds):
            current_time[0] += seconds

        with patch("fotura.utils.operation_throttle.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: current_time[0]
            mock_time.sleep.side_effect = advance_time

            throttle = OperationThrottle(max_operations=2, window_seconds=1.0)
            for _ in range(3):
                with throttle:
                    pass

            mock_time.sleep.assert_called()
            assert current_time[0] >= 1.0

    def test_releases_after_window_expires(self):
        current_time = [0.0]

        with patch("fotura.utils.operation_throttle.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: current_time[0]

            throttle = OperationThrottle(max_operations=2, window_seconds=1.0)
            for _ in range(2):
                with throttle:
                    pass

            # Move past the window
            current_time[0] = 1.5

            for _ in range(2):
                with throttle:
                    pass

            mock_time.sleep.assert_not_called()
