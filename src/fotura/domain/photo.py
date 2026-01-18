import logging
from pathlib import Path

from fotura.domain.media_file import MediaFile

logger = logging.getLogger(__name__)


class Photo(MediaFile):
    def __init__(self, path: Path):
        super().__init__(path)
