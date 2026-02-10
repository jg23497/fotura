import threading
import time
from collections import deque
from typing import Deque


class OperationThrottle:
    """
    Thread-safe rate limiter that restricts operations to a maximum
    number per time window, using a sliding window algorithm.

    Example: OperationThrottle(max_operations=50, window_seconds=60)
    limits to 50 operations per minute.
    """

    def __init__(self, max_operations: int, window_seconds: float) -> None:
        self.max_operations = max_operations
        self.window_seconds = window_seconds
        self.__timestamps: Deque[float] = deque()
        self.__lock = threading.Lock()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def acquire(self) -> None:
        while True:
            with self.__lock:
                window_start_time = self.__get_window_start_time()
                self.__prune_timestamps_outside_of_window(window_start_time)

                if self.__has_capacity():
                    self.__append_current_time()
                    return

                # Let the oldest operation fall out of the window
                sleep_time = self.__timestamps[0] - window_start_time

            # Sleep outside the lock
            if sleep_time > 0:
                time.sleep(sleep_time)

    def __get_window_start_time(self) -> float:
        now = time.monotonic()
        return now - self.window_seconds

    def __prune_timestamps_outside_of_window(self, window_start_time: float) -> None:
        while self.__timestamps and self.__timestamps[0] <= window_start_time:
            self.__timestamps.popleft()

    def __has_capacity(self) -> bool:
        return len(self.__timestamps) < self.max_operations

    def __append_current_time(self) -> None:
        self.__timestamps.append(time.monotonic())
