import logging
from enum import Enum
from pathlib import Path
from typing import Collection, Iterator

from fotura.domain.media_file import MediaFile
from fotura.domain.photo import Photo
from fotura.domain.video_file import VideoFile
from fotura.reporting.report_category import ReportCategory

logger = logging.getLogger(__name__)

PHOTO_RAW_EXTENSIONS = {
    ".arw",
    ".nef",
    ".cr2",
    ".orf",
    ".pef",
    ".dng",
    ".raw",
    ".raf",
}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".tif"} | PHOTO_RAW_EXTENSIONS

VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".3gp",
    ".3g2",
}


class MediaType(str, Enum):
    PHOTOS = "photos"
    VIDEOS = "videos"


class MediaFinder:
    def __init__(
        self,
        input_path: Path,
        media_types: Collection[MediaType] = (MediaType.PHOTOS,),
    ):
        self.input_path = input_path
        self.__supported_extensions = set()
        if MediaType.PHOTOS in media_types:
            self.__supported_extensions.update(PHOTO_EXTENSIONS)
        if MediaType.VIDEOS in media_types:
            self.__supported_extensions.update(VIDEO_EXTENSIONS)

    def find(self) -> Iterator[MediaFile]:
        for file_path in sorted(self.input_path.rglob("*")):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in self.__supported_extensions:
                logger.warning(
                    "Ignored %s (%s extension not in supported list)",
                    file_path,
                    file_extension,
                    extra={
                        "media_file": file_path,
                        "report_category": ReportCategory.ignored,
                    },
                )
                continue

            if file_extension in VIDEO_EXTENSIONS:
                yield VideoFile(file_path)
            else:
                yield Photo(file_path)

    @staticmethod
    def media_file_for(path: Path) -> MediaFile:
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            return VideoFile(path)
        return Photo(path)
