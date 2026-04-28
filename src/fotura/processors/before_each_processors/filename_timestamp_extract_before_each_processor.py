import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fotura.domain.photo import Photo
from fotura.io.photos.exif.exif_data import ExifData
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType

from .before_each_processor import BeforeEachProcessor

logger = logging.getLogger(__name__)


class FilenameTimestampExtractBeforeEachProcessor(BeforeEachProcessor):
    _WHATSAPP_REGEX = re.compile(r"^IMG-(\d{4})(\d{2})(\d{2})-WA\d{4}.*")
    _ANDROID_REGEX = re.compile(r"^IMG_(\d{8})_(\d{6})")

    def __init__(self, context: Context) -> None:
        self.context = context

    def can_handle(self, photo: Photo) -> bool:
        return self.__get_handler(photo.path.name) is not None

    def process(self, photo: Photo) -> Optional[Dict[FactType, datetime]]:
        filename = photo.path.name
        handler = self.__get_handler(filename)
        if not handler:
            return None

        date: Optional[datetime] = handler(self, filename)
        if not date:
            raise ValueError(f"Unable to extract timestamp from {filename}")

        photo.log(
            logging.INFO,
            "Updated EXIF date fields to %s",
            date.strftime("%Y/%m/%d %H:%M:%S"),
        )

        if not self.context.dry_run:
            ExifData.write_date(photo, date)

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
