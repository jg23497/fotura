from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, TypeGuard, TypeVar

from fotura.domain.media_file import MediaFile
from fotura.processors.fact_type import FactType

TMediaFile = TypeVar("TMediaFile", bound=MediaFile)


class AfterEachProcessor(ABC, Generic[TMediaFile]):
    @abstractmethod
    def can_handle(self, media_file: MediaFile) -> TypeGuard[TMediaFile]:
        pass

    @abstractmethod
    def process(self, media_file: TMediaFile) -> Optional[Dict[FactType, Any]]:
        pass

    def configure(self) -> None:
        pass
