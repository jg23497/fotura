import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from fotura.domain.media_file import MediaFile
from fotura.integrations.google_photos.client import TALLY_KEY
from fotura.integrations.google_photos.uploader import GooglePhotosUploader
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.processors.after_all_processors.after_all_processor import AfterAllProcessor
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.processors.resumable import Resumable

logger = logging.getLogger(__name__)


class GooglePhotosUploadAfterAllProcessor(AfterAllProcessor[MediaFile], Resumable):
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
        self, media_files: List[MediaFile]
    ) -> Optional[Dict[MediaFile, Dict[FactType, Any]]]:
        supported_media_files = []

        for media_file in media_files:
            if self.__uploader.can_support(media_file):
                supported_media_files.append(media_file)
            else:
                media_file.log(logging.DEBUG, "Skipping unsupported file type")

        if not supported_media_files:
            return None

        for batch in self.chunked(supported_media_files, self.batch_size):
            self.__process_batch(batch)

        return None

    def get_retryable(self) -> Iterator[MediaFile]:
        rows = self.__repository.find_retryable()
        for row in rows:
            yield MediaFile(Path(row["file_path"]))

    def resume(self) -> None:
        items = list(self.get_retryable())
        supported_items = [i for i in items if self.__uploader.can_support(i)]

        if not supported_items:
            logger.info("No retryable uploads found")
            return

        for batch in self.chunked(supported_items, self.batch_size):
            self.__process_batch(batch)

    def __process_batch(self, media_files: List[MediaFile]) -> None:
        if self.dry_run:
            for media_file in media_files:
                media_file.log(logging.INFO, "Uploaded to Google Photos")
                self.context.tally.increment(TALLY_KEY)
            return

        upload_tokens = self.__uploader.upload_bytes_concurrent(
            media_files, self.concurrency
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
    def chunked(items: List[MediaFile], chunk_size: int) -> Iterator[List[MediaFile]]:
        """Yield successive chunks of the given size."""
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]
