from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from fotura.domain.photo import Photo
from fotura.processors.fact_type import FactType


class AfterAllProcessor(ABC):
    @abstractmethod
    def process(
        self, photos: List[Photo]
    ) -> Optional[Dict[Photo, Dict[FactType, Any]]]:
        pass

    def configure(self) -> None:
        pass
