from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar

from fotura.domain.media_file import MediaFile
from fotura.processors.fact_type import FactType

TMediaFile = TypeVar("TMediaFile", bound=MediaFile)


class AfterAllProcessor(ABC, Generic[TMediaFile]):
    @abstractmethod
    def process(
        self, media_files: List[TMediaFile]
    ) -> Optional[Dict[TMediaFile, Dict[FactType, Any]]]:
        pass

    def configure(self) -> None:
        pass
