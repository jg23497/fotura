import logging
from datetime import datetime
from typing import Optional

import piexif

from fotura.domain.photo import Photo
from fotura.io.photos.exif.exif_io_strategy import ExifIoStrategy

logger = logging.getLogger(__name__)


class PiexifExifStrategy(ExifIoStrategy):
    def extract_date(self, photo: Photo) -> Optional[datetime]:
        try:
            return self.__parse_timestamp(piexif.load(str(photo.path)))
        except Exception:
            photo.log(logging.ERROR, "Error reading EXIF data", exc_info=True)
            return None

    def extract_date_from_bytes(
        self, jpeg_bytes: bytes, photo: Photo
    ) -> Optional[datetime]:
        try:
            return self.__parse_timestamp(piexif.load(jpeg_bytes))
        except Exception:
            photo.log(logging.ERROR, "Error reading EXIF data", exc_info=True)
            return None

    def write_date(self, photo: Photo, timestamp: datetime) -> None:
        exif = piexif.load(str(photo.path))
        formatted_date: str = timestamp.strftime("%Y:%m:%d %H:%M:%S")

        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = formatted_date
        exif["Exif"][piexif.ExifIFD.DateTimeDigitized] = formatted_date
        exif["0th"][piexif.ImageIFD.DateTime] = formatted_date

        exif_bytes = piexif.dump(exif)
        piexif.insert(exif_bytes, str(photo.path))

    @staticmethod
    def __parse_timestamp(exif_dict) -> Optional[datetime]:
        date_fields = [
            (piexif.ExifIFD.DateTimeOriginal, "Exif"),
            (piexif.ExifIFD.DateTimeDigitized, "Exif"),
            (piexif.ImageIFD.DateTime, "0th"),
        ]
        for field, ifd in date_fields:
            if ifd in exif_dict and field in exif_dict[ifd]:
                date_str = exif_dict[ifd][field].decode("utf-8")
                try:
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue
        return None
