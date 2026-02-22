import logging
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from fotura.domain.photo import Photo
from fotura.integrations.google_photos.uploader import GooglePhotosUploader
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.processors.after_each_processors.after_each_processor import (
    AfterEachProcessor,
)
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.processors.resumable import Resumable

logger = logging.getLogger(__name__)


class GooglePhotosUploadAfterEachProcessor(AfterEachProcessor, Resumable):
    def __init__(self, context: Context) -> None:
        self.context = context
        self.dry_run = context.dry_run
        self.__repository = GooglePhotosUploadRepository(context.database)
        self.__uploader = GooglePhotosUploader(context, self.__repository)

    def configure(self) -> None:
        self.__uploader.configure()

    def can_handle(self, photo: Photo) -> bool:
        return self.__uploader.can_support(photo)

    def process(self, photo: Photo) -> Optional[Dict[FactType, Any]]:
        if self.dry_run:
            photo.log(logging.INFO, "Uploaded to Google Photos")
            self.context.tally.increment("uploaded to google photos")
            return None

        try:
            upload_token = self.__uploader.upload_bytes(photo)
            self.__uploader.create_media_item(photo, upload_token)
        except Exception:
            photo.log(logging.ERROR, "Failed to upload to Google Photos", exc_info=True)
            raise

        return None

    def get_retryable(self) -> Iterator[Photo]:
        rows = self.__repository.find_retryable()
        for row in rows:
            yield Photo(Path(row["file_path"]))

    def resume(self) -> None:
        items = list(self.get_retryable())
        if not items:
            logger.info("No retryable uploads found")
            return

        for item in items:
            if self.__uploader.can_support(item):
                self.process(item)
