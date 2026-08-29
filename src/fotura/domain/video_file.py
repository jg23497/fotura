from pathlib import Path

from fotura.domain.media_file import MediaFile


class VideoFile(MediaFile):
    def __init__(self, path: Path):
        super().__init__(path)
