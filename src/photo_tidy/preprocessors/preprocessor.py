from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Any

from photo_tidy.preprocessors.fact_type import FactType


class Preprocessor(ABC):
    @abstractmethod
    def can_handle(self, image_path: Path) -> bool:
        pass

    @abstractmethod
    def process(self, image_path: Path) -> Optional[Dict[FactType, Any]]:
        pass

    def set_up(self) -> None:
        pass
