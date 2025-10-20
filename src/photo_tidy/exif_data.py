import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import piexif

logger = logging.getLogger(__name__)


class ExifData:
    @staticmethod
    def extract_date(image_path: Path) -> Optional[datetime]:
        """
        Extracts the capture date and time from an image's EXIF metadata.

        This method attempts to read EXIF data from the provided image file
        and checks common date fields in order of priority:
          1. DateTimeOriginal (Exif)
          2. DateTimeDigitized (Exif)
          3. DateTime (0th IFD)

        If a valid date string is found, it is converted into a datetime object.
        If no valid date is found or parsing fails, None is returned.

        Args:
            image_path (Path): Path to the image file.

        Returns:
            Optional[datetime]: A datetime object representing the image's
                                capture date, or None if unavailable.
        """
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

    @staticmethod
    def write_date(image_path: Path, timestamp: datetime) -> None:
        """
        Writes or updates the capture date in an image's EXIF metadata.

        This method sets the given timestamp in the following EXIF fields:
          - DateTimeOriginal (Exif)
          - DateTimeDigitized (Exif)
          - DateTime (0th IFD)

        The date is stored in the format 'YYYY:MM:DD HH:MM:SS'.
        The updated EXIF metadata is then written back into the image file.

        Args:
            image_path (Path): Path to the image file to be updated.
            timestamp (datetime): The datetime value to write into EXIF.
        """
        exif = piexif.load(str(image_path))
        formatted_date: str = timestamp.strftime("%Y:%m:%d %H:%M:%S")

        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = formatted_date
        exif["Exif"][piexif.ExifIFD.DateTimeDigitized] = formatted_date
        exif["0th"][piexif.ImageIFD.DateTime] = formatted_date

        exif_bytes = piexif.dump(exif)
        piexif.insert(exif_bytes, str(image_path))
