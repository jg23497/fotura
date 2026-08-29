import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from tenacity import (
    Retrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from fotura.domain.media_file import MediaFile
from fotura.integrations.google_photos.client import (
    TALLY_KEY,
    GooglePhotosClient,
)
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.persistence.upload_status import UploadStatus
from fotura.processors.context import Context
from fotura.processors.processor_setup_error import ProcessorSetupError
from fotura.utils.operation_throttle import OperationThrottle

SUPPORTED_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".ico",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

logger = logging.getLogger(__name__)


class GooglePhotosUploader:
    def __init__(
        self,
        context: Context,
        repository: GooglePhotosUploadRepository,
    ) -> None:
        self._context = context
        self._client = GooglePhotosClient(context.user_config_path)
        self._batch_create_throttle = OperationThrottle(
            max_operations=50, window_seconds=60
        )
        self.__repository = repository

    def configure(self) -> None:
        self._client.configure()

    def can_support(self, media_file: MediaFile) -> bool:
        if media_file.path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.debug("Skipping file with unsupported format: %s", media_file.path)
            return False
        try:
            within_size_limit = media_file.path.stat().st_size <= MAX_FILE_SIZE
            if not within_size_limit:
                media_file.log(
                    logging.WARNING,
                    "Google Photos: Skipping file exceeding %sMB size limit",
                    MAX_FILE_SIZE / (1024 * 1024),
                )
            return within_size_limit
        except OSError:
            logger.debug(
                "Failed to get file size for %s. The file may not exist or is inaccessible.",
                media_file.path,
            )
            return False

    def upload_bytes(self, media_file: MediaFile) -> str:
        """Upload bytes with DB status tracking. Raises on failure."""
        self.__repository.upsert_pending(media_file.path)
        self.__repository.update_status(media_file.path, UploadStatus.UPLOADING)

        media_file.log(logging.INFO, "Uploading media file to Google Photos...")
        try:
            return self.__upload_bytes(media_file)
        except Exception:
            self.__repository.update_status(media_file.path, UploadStatus.FAILED)
            raise

    def __upload_bytes(self, media_file: MediaFile) -> str:
        """Upload bytes with exponential backoff retry. Raises on failure."""
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_not_exception_type(ProcessorSetupError),
            before_sleep=lambda retry_state: media_file.log(
                logging.WARNING,
                "Upload failed, retrying: %s",
                retry_state.outcome.exception(),
            ),
            reraise=True,
        ):
            with attempt:
                upload_token = self._client.upload_bytes(str(media_file.path))

        return upload_token

    def upload_bytes_concurrent(
        self, media_files: List[MediaFile], concurrency: int
    ) -> List[Tuple[MediaFile, str]]:
        """Upload bytes for multiple media files using a thread pool."""
        upload_tokens: List[Tuple[MediaFile, str]] = []

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_media_file = {
                executor.submit(self.__try_upload_bytes, media_file): media_file
                for media_file in media_files
            }

            for future in as_completed(future_to_media_file):
                media_file = future_to_media_file[future]
                token = future.result()
                if token:
                    upload_tokens.append((media_file, token))

        return upload_tokens

    def create_media_item(self, media_file: MediaFile, token: str) -> None:
        """Create a single media item (throttled). Raises on failure."""
        with self._batch_create_throttle:
            response = self._client.create_media_item(token, media_file.path.name)

        self.__record_upload(media_file, response["newMediaItemResults"][0])

    def create_media_items(self, upload_tokens: List[Tuple[MediaFile, str]]) -> None:
        """Batch create media items (throttled). Retries failures individually."""
        try:
            items = [
                (media_file.path.name, token) for media_file, token in upload_tokens
            ]
            with self._batch_create_throttle:
                response = self._client.create_media_items(items)
        except Exception:
            for media_file, _ in upload_tokens:
                media_file.log(
                    logging.ERROR, "Failed to create media item in batch", exc_info=True
                )
                self._context.tally.increment("errored")
            return

        failed_media_files = self.__process_batch_results(response, upload_tokens)

        for media_file in failed_media_files:
            self.__retry_single_media_file(media_file)

    def __process_batch_results(
        self,
        response: dict,
        upload_tokens: List[Tuple[MediaFile, str]],
    ) -> List[MediaFile]:
        """Process a batch-create response and return failed media files."""
        failed_media_files: List[MediaFile] = []
        results = response.get("newMediaItemResults", [])

        for i, result in enumerate(results):
            if i >= len(upload_tokens):
                break

            media_file = upload_tokens[i][0]

            if "mediaItem" in result:
                self.__record_upload(media_file, result)
                continue

            error = result.get("status", {}).get("message", "Unknown error")

            media_file.log(
                logging.WARNING,
                "Failed to create media item: %s (scheduling retry)",
                error,
            )

            failed_media_files.append(media_file)

        return failed_media_files

    def __retry_single_media_file(self, media_file: MediaFile) -> None:
        media_file.log(logging.DEBUG, "Retrying with fresh upload")
        token = self.__try_upload_bytes(media_file)
        if token:
            self.__try_create_media_item(media_file, token)

    def __try_upload_bytes(self, media_file: MediaFile) -> Optional[str]:
        try:
            return self.upload_bytes(media_file)
        except ProcessorSetupError:
            raise
        except Exception:
            media_file.log(
                logging.ERROR,
                "Failed to upload after all retry attempts",
                exc_info=True,
            )
            self._context.tally.increment("errored")
            return None

    def __try_create_media_item(self, media_file: MediaFile, token: str) -> None:
        """Create a single media item (throttled), with error handling."""
        try:
            with self._batch_create_throttle:
                response = self._client.create_media_item(token, media_file.path.name)

            result = response.get("newMediaItemResults", [{}])[0]

            if "mediaItem" in result:
                self.__record_upload(media_file, result)
            else:
                error = result.get("status", {}).get("message", "Unknown error")
                media_file.log(logging.ERROR, "Failed to create media item: %s", error)
                self.__mark_failed(media_file)
                self._context.tally.increment("errored")
        except Exception:
            media_file.log(logging.ERROR, "Failed to create media item", exc_info=True)
            self.__mark_failed(media_file)
            self._context.tally.increment("errored")

    def __record_upload(self, media_file: MediaFile, result: dict) -> None:
        url = result["mediaItem"].get("productUrl", "")
        media_file.log(logging.INFO, "Uploaded to Google Photos: %s", url)
        self._context.tally.increment(TALLY_KEY)
        self.__repository.update_status(media_file.path, UploadStatus.UPLOADED, url)

    def __mark_failed(self, media_file: MediaFile) -> None:
        self.__repository.update_status(media_file.path, UploadStatus.FAILED)
