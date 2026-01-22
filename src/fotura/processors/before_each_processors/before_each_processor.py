from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from fotura.domain.photo import Photo
from fotura.processors.fact_type import FactType


class BeforeEachProcessor(ABC):
    @abstractmethod
    def can_handle(self, photo: Photo) -> bool:
        pass

    @abstractmethod
    def process(self, photo: Photo) -> Optional[Dict[FactType, Any]]:
        pass

    def configure(self) -> None:
        pass
