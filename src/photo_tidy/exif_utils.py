from datetime import datetime
from typing import Optional
import piexif
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ExifDateExtractor:
    @staticmethod
    def extract_date(image_path: Path) -> Optional[datetime]:
        try:
            exif_dict = piexif.load(str(image_path))

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

            logger.warning(f"No EXIF date found in {image_path}")
            return None

        except Exception as e:
            logger.error(f"Error reading EXIF data from {image_path}: {str(e)}")
            return None
