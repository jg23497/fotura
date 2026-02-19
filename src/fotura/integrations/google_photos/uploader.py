import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from tenacity import (
    Retrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from fotura.domain.photo import Photo
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

    def can_support(self, photo: Photo) -> bool:
        if photo.path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        try:
            return photo.path.stat().st_size <= MAX_FILE_SIZE
        except OSError:
            return False

    def upload_bytes(self, photo: Photo) -> str:
        """Upload bytes with DB status tracking. Raises on failure."""
        self.__repository.upsert_pending(photo.path)
        self.__repository.update_status(photo.path, UploadStatus.UPLOADING)

        photo.log(logging.INFO, "Uploading image to Google Photos...")
        try:
            return self.__upload_bytes(photo)
        except Exception:
            self.__repository.update_status(photo.path, UploadStatus.FAILED)
            raise

    def __upload_bytes(self, photo: Photo) -> str:
        """Upload bytes with exponential backoff retry. Raises on failure."""
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_not_exception_type(ProcessorSetupError),
            before_sleep=lambda retry_state: photo.log(
                logging.WARNING,
                "Upload failed, retrying: %s",
                retry_state.outcome.exception(),
            ),
            reraise=True,
        ):
            with attempt:
                upload_token = self._client.upload_bytes(str(photo.path))

        return upload_token

    def upload_bytes_concurrent(
        self, photos: List[Photo], concurrency: int
    ) -> List[Tuple[Photo, str]]:
        """Upload bytes for multiple photos currently using thread pool."""
        upload_tokens: List[Tuple[Photo, str]] = []

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_photo = {
                executor.submit(self.__try_upload_bytes, photo): photo
                for photo in photos
            }

            for future in as_completed(future_to_photo):
                photo = future_to_photo[future]
                token = future.result()
                if token:
                    upload_tokens.append((photo, token))

        return upload_tokens

    def create_media_item(self, photo: Photo, token: str) -> None:
        """Create a single media item (throttled). Raises on failure."""
        with self._batch_create_throttle:
            response = self._client.create_media_item(token, photo.path.name)

        self.__record_upload(photo, response["newMediaItemResults"][0])

    def create_media_items(self, upload_tokens: List[Tuple[Photo, str]]) -> None:
        """Batch create media items (throttled). Retries failures individually."""
        try:
            items = [(photo.path.name, token) for photo, token in upload_tokens]
            with self._batch_create_throttle:
                response = self._client.create_media_items(items)
        except Exception:
            for photo, _ in upload_tokens:
                photo.log(
                    logging.ERROR, "Failed to create media item in batch", exc_info=True
                )
                self._context.tally.increment("errored")
            return

        failed_photos = self.__process_batch_results(response, upload_tokens)

        for photo in failed_photos:
            self.__retry_single_photo(photo)

    def __process_batch_results(
        self,
        response: dict,
        upload_tokens: List[Tuple[Photo, str]],
    ) -> List[Photo]:
        """Process batch create response. Returns photos that failed."""
        failed_photos: List[Photo] = []
        results = response.get("newMediaItemResults", [])

        for i, result in enumerate(results):
            if i >= len(upload_tokens):
                break

            photo = upload_tokens[i][0]

            if "mediaItem" in result:
                self.__record_upload(photo, result)
                continue

            error = result.get("status", {}).get("message", "Unknown error")

            photo.log(
                logging.WARNING,
                "Failed to create media item: %s (scheduling retry)",
                error,
            )

            failed_photos.append(photo)

        return failed_photos

    def __retry_single_photo(self, photo: Photo) -> None:
        photo.log(logging.DEBUG, "Retrying with fresh upload")
        token = self.__try_upload_bytes(photo)
        if token:
            self.__try_create_media_item(photo, token)

    def __try_upload_bytes(self, photo: Photo) -> Optional[str]:
        try:
            return self.upload_bytes(photo)
        except ProcessorSetupError:
            raise
        except Exception:
            photo.log(
                logging.ERROR,
                "Failed to upload after all retry attempts",
                exc_info=True,
            )
            self._context.tally.increment("errored")
            return None

    def __try_create_media_item(self, photo: Photo, token: str) -> None:
        """Create a single media item (throttled), with error handling."""
        try:
            with self._batch_create_throttle:
                response = self._client.create_media_item(token, photo.path.name)

            result = response.get("newMediaItemResults", [{}])[0]

            if "mediaItem" in result:
                self.__record_upload(photo, result)
            else:
                error = result.get("status", {}).get("message", "Unknown error")
                photo.log(logging.ERROR, "Failed to create media item: %s", error)
                self.__mark_failed(photo)
                self._context.tally.increment("errored")
        except Exception:
            photo.log(logging.ERROR, "Failed to create media item", exc_info=True)
            self.__mark_failed(photo)
            self._context.tally.increment("errored")

    def __record_upload(self, photo: Photo, result: dict) -> None:
        url = result["mediaItem"].get("productUrl", "")
        photo.log(logging.INFO, "Uploaded to Google Photos: %s", url)
        self._context.tally.increment(TALLY_KEY)
        self.__repository.update_status(photo.path, UploadStatus.UPLOADED, url)

    def __mark_failed(self, photo: Photo) -> None:
        self.__repository.update_status(photo.path, UploadStatus.FAILED)
