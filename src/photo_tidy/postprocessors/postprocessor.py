from abc import ABC, abstractmethod
from pathlib import Path


class Postprocessor(ABC):
    @abstractmethod
    def can_handle(self, image_path: Path) -> bool:
        pass

    @abstractmethod
    def process(self, image_path: Path) -> None:
        pass

    def configure(self) -> None:
        pass
