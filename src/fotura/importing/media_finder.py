import logging
from pathlib import Path
from typing import Iterator

from fotura.domain.photo import Photo

logger = logging.getLogger(__name__)

PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".arw",
    ".nef",
    ".cr2",
    ".orf",
    ".pef",
    ".dng",
    ".raw",
    ".raf",
}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".3gp",
    ".3g2",
}


class MediaFinder:
    def __init__(self, input_path: Path, include_videos: bool = False):
        self.input_path = input_path
        self.__supported_extensions = PHOTO_EXTENSIONS
        if include_videos:
            self.__supported_extensions = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS

    def find(self) -> Iterator[Path]:
        for file_path in sorted(self.input_path.rglob("*")):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in self.__supported_extensions:
                logger.warning(
                    "Ignored %s (%s extension not in supported list)",
                    file_path,
                    file_extension,
                )
                continue

            yield Photo(file_path)
