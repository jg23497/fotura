from datetime import datetime
from typing import Optional

from fotura.domain.photo import Photo
from fotura.io.photos.exif.exif_io_strategy import ExifIoStrategy
from fotura.io.photos.exif.piexif_exif_strategy import PiexifExifStrategy
from fotura.io.photos.exif.raf_exif_strategy import RafExifStrategy

_STRATEGY_DEFAULT: ExifIoStrategy = PiexifExifStrategy()

_STRATEGIES: dict[str, ExifIoStrategy] = {
    ".raf": RafExifStrategy(),
}


class ExifData:
    @staticmethod
    def extract_date(photo: Photo) -> Optional[datetime]:
        return ExifData.__strategy_for(photo).extract_date(photo)

    @staticmethod
    def write_date(photo: Photo, timestamp: datetime) -> None:
        ExifData.__strategy_for(photo).write_date(photo, timestamp)

    @staticmethod
    def __strategy_for(photo: Photo) -> ExifIoStrategy:
        return _STRATEGIES.get(photo.path.suffix.lower(), _STRATEGY_DEFAULT)
