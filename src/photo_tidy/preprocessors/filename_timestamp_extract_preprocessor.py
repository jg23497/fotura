from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import re
import logging

from photo_tidy.exif_data import ExifData
from photo_tidy.preprocessors.fact_type import FactType
from photo_tidy.processors.context import Context
from .preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class FilenameTimestampExtractPreprocessor(Preprocessor):
    _WHATSAPP_REGEX = re.compile(r"^IMG-(\d{4})(\d{2})(\d{2})-WA\d{4}.*")
    _ANDROID_REGEX = re.compile(r"^IMG_(\d{8})_(\d{6})")

    def __init__(self, context: Context) -> None:
        self.dry_run = context.dry_run

    def can_handle(self, image_path: Path) -> bool:
        return self.__get_handler(image_path.name) is not None

    def process(self, image_path: Path) -> Optional[Dict[FactType, datetime]]:
        filename = image_path.name
        handler = self.__get_handler(filename)
        if not handler:
            return None

        date: Optional[datetime] = handler(self, filename)
        if not date:
            raise ValueError(f"Unable to extract timestamp from {filename}")

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would update EXIF date fields for {image_path.name} to {date.strftime('%Y:%m:%d %H:%M:%S')}"
            )
        else:
            ExifData.write_date(image_path, date)

        return {FactType.TAKEN_TIMESTAMP: date}

    def __get_handler(self, filename: str) -> Optional[object]:
        for regex, handler in self.__HANDLERS:
            if regex.match(filename):
                return handler
        return None

    def __extract_whatsapp(self, filename: str) -> Optional[datetime]:
        match = self._WHATSAPP_REGEX.search(filename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day, 12, 0, 0)
        return None

    def __extract_android(self, filename: str) -> Optional[datetime]:
        match = self._ANDROID_REGEX.search(filename)
        if match:
            date_str, time_str = match.groups()
            return datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
        return None

    __HANDLERS: List[Tuple[re.Pattern, object]] = [
        (_WHATSAPP_REGEX, __extract_whatsapp),
        (_ANDROID_REGEX, __extract_android),
    ]
