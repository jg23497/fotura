from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import piexif
import re
import logging

from photo_tidy.preprocessors.fact_type import FactType
from .preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class WhatsAppPreprocessor(Preprocessor):
    """Preprocessor for WhatsApp images that extracts the taken timestamp
    from the filename and updates the image's EXIF data."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def can_handle(self, image_path: Path) -> bool:
        filename = image_path.name
        return bool(re.match(r"^IMG-\d{8}-WA\d{4}.*", filename))

    def process(self, image_path: Path) -> Optional[Dict[FactType, datetime]]:
        filename = image_path.name
        match = re.search(r"^IMG-(\d{4})(\d{2})(\d{2})-WA\d{4}.*", filename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            date = datetime(year, month, day)

            try:
                exif_dict = piexif.load(str(image_path))

                # Update DateTimeOriginal
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime(
                    year, month, day, 4, 0, 0
                ).strftime("%Y:%m:%d %H:%M:%S")
                # Update DateTimeDigitized
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = datetime(
                    year, month, day, 4, 0, 0
                ).strftime("%Y:%m:%d %H:%M:%S")
                # Update DateTime
                exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime(
                    year, month, day, 4, 0, 0
                ).strftime("%Y:%m:%d %H:%M:%S")

                if self.dry_run:
                    logger.info(
                        f"[DRY RUN] Would update EXIF date fields for {image_path.name} to {date.strftime('%Y-%m-%d')}"
                    )
                else:
                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, str(image_path))
                    logger.info(f"Updated EXIF date fields for {image_path.name}")
            except Exception as e:
                logger.error(
                    f"Error updating EXIF data for {image_path.name}: {str(e)}"
                )

            return {FactType.TAKEN_TIMESTAMP: date}
        return None
