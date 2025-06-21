from datetime import datetime
from abc import ABC, abstractmethod


class ReportItem(ABC):
    def __init__(self):
        self.timestamp = datetime.now()

    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def as_dict(self) -> str:
        pass

    def __repr__(self) -> str:
        description = ", ".join(f"{k}: {v}" for k, v in self.as_dict().items())
        return f"[{self.name()}] {description}"
