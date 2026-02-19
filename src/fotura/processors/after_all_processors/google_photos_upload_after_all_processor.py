import logging
from typing import Any, Dict, Iterator, List, Optional

from fotura.domain.photo import Photo
from fotura.integrations.google_photos.client import TALLY_KEY
from fotura.integrations.google_photos.uploader import GooglePhotosUploader
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.processors.after_all_processors.after_all_processor import AfterAllProcessor
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType


class GooglePhotosUploadAfterAllProcessor(AfterAllProcessor):
    DEFAULT_CONCURRENCY = 2
    DEFAULT_BATCH_SIZE = 10
    MAX_CONCURRENCY = 5
    MAX_BATCH_SIZE = 50

    def __init__(
        self,
        context: Context,
        concurrency: int = DEFAULT_CONCURRENCY,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.context = context
        self.dry_run = context.dry_run
        self.concurrency = concurrency
        self.batch_size = batch_size

        self.__validate()
        self.__repository = GooglePhotosUploadRepository(context.database)
        self.__uploader = GooglePhotosUploader(context, self.__repository)

    def configure(self) -> None:
        self.__uploader.configure()

    def process(
        self, photos: List[Photo]
    ) -> Optional[Dict[Photo, Dict[FactType, Any]]]:
        supported_photos = []

        for photo in photos:
            if self.__uploader.can_support(photo):
                supported_photos.append(photo)
            else:
                photo.log(logging.DEBUG, "Skipping unsupported file type")

        if not supported_photos:
            return None

        for batch in self.chunked(supported_photos, self.batch_size):
            self.__process_batch(batch)

        return None

    def __process_batch(self, photos: List[Photo]) -> None:
        if self.dry_run:
            for photo in photos:
                photo.log(logging.INFO, "Uploaded to Google Photos")
                self.context.tally.increment(TALLY_KEY)
            return

        upload_tokens = self.__uploader.upload_bytes_concurrent(
            photos, self.concurrency
        )

        if upload_tokens:
            self.__uploader.create_media_items(upload_tokens)

    def __validate(self):
        if not 1 <= self.concurrency <= self.MAX_CONCURRENCY:
            raise ValueError(
                f"concurrency must be between 1 and {self.MAX_CONCURRENCY}, "
                f"got {self.concurrency}"
            )
        if not 1 <= self.batch_size <= self.MAX_BATCH_SIZE:
            raise ValueError(
                f"batch_size must be between 1 and {self.MAX_BATCH_SIZE}, "
                f"got {self.batch_size}"
            )

    @staticmethod
    def chunked(items: List[Photo], chunk_size: int) -> Iterator[List[Photo]]:
        """Yield successive chunks of the given size."""
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]
