from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from fotura.domain.photo import Photo


class ExifIoStrategy(ABC):
    @abstractmethod
    def extract_date(self, photo: Photo) -> Optional[datetime]: ...

    @abstractmethod
    def write_date(self, photo: Photo, timestamp: datetime) -> None: ...
