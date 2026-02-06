from collections import Counter
from threading import Lock
from typing import Dict


class SynchronizedCounter:
    def __init__(self, initial: Dict[str, int] = {}):
        self.counter = Counter(initial)
        self.lock = Lock()

    def increment(self, key: str) -> None:
        with self.lock:
            self.counter[key] += 1

    def get_snapshot(self) -> Dict[str, int]:
        with self.lock:
            return dict(self.counter)
