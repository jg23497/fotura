import logging
from pathlib import Path
from typing import Iterator

from fotura.domain.photo import Photo

logger = logging.getLogger(__name__)


class MediaFinder:
    SUPPORTED_EXTENSIONS = {
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
    }

    def __init__(self, input_path: Path):
        self.input_path = input_path

    def find(self) -> Iterator[Path]:
        for file_path in sorted(self.input_path.rglob("*")):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in self.SUPPORTED_EXTENSIONS:
                logger.warning(
                    "Ignored %s (%s extension not in supported list)",
                    file_path,
                    file_extension,
                )
                continue

            yield Photo(file_path)
