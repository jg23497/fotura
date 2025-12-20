from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from fotura.preprocessors.fact_type import FactType


class Postprocessor(ABC):
    @abstractmethod
    def can_handle(self, image_path: Path) -> bool:
        pass

    @abstractmethod
    def process(
        self, image_path: Path, facts: Dict[FactType, Any]
    ) -> Optional[Dict[FactType, Any]]:
        pass

    def configure(self) -> None:
        pass
