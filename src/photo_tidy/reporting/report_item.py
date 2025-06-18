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

    @abstractmethod
    def __str__(self) -> str:
        pass

    def __repr__(self) -> str:
        return f"{self.timestamp}"
