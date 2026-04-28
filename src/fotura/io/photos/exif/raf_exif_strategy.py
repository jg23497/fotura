import logging
import struct
from datetime import datetime
from typing import Optional

from fotura.domain.photo import Photo
from fotura.io.photos.exif.exif_io_strategy import ExifIoStrategy
from fotura.io.photos.exif.piexif_exif_strategy import PiexifExifStrategy

logger = logging.getLogger(__name__)

_piexif_strategy = PiexifExifStrategy()


class RafExifStrategy(ExifIoStrategy):
    def extract_date(self, photo: Photo) -> Optional[datetime]:
        try:
            with open(photo.path, "rb") as f:
                # RAF header layout: after a 68-byte magic/version/camera block,
                # there are three 8-byte directory entries (JPEG, RAW, metadata).
                # Offset 84 = 68 + 16, i.e. the second entry, which points at the
                # embedded full-resolution JPEG preview.
                f.seek(84)
                # Each entry is two big-endian uint32s: absolute file offset then length.
                jpeg_offset, jpeg_length = struct.unpack(">II", f.read(8))
                f.seek(jpeg_offset)
                jpeg_bytes = f.read(jpeg_length)
            return _piexif_strategy.extract_date_from_bytes(jpeg_bytes, photo)
        except Exception:
            photo.log(logging.ERROR, "Error reading EXIF data", exc_info=True)
            return None

    def write_date(self, photo: Photo, timestamp: datetime) -> None:
        raise NotImplementedError("EXIF write not supported for RAF files")
