from pathlib import Path
import logging
from photo_tidy.postprocessors.postprocessor import Postprocessor

logger = logging.getLogger(__name__)


class GooglePhotosUploadPostprocessor(Postprocessor):
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def can_handle(self, image_path: Path) -> bool:
        return True

    def process(self, image_path: Path) -> None:
        logger.info(f"Pretending to upload {image_path} to Google Photos API")
        pass
