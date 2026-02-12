import logging
from typing import Any, Dict, Optional

from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_exponential

from fotura.domain.photo import Photo
from fotura.integrations.google_photos import GooglePhotosClient
from fotura.integrations.google_photos.client import SUPPORTED_EXTENSIONS, TALLY_KEY
from fotura.processors.after_each_processors.after_each_processor import (
    AfterEachProcessor,
)
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.processors.processor_setup_error import ProcessorSetupError

logger = logging.getLogger(__name__)


class GooglePhotosUploadAfterEachProcessor(AfterEachProcessor):
    def __init__(self, context: Context) -> None:
        self.context = context
        self.dry_run = context.dry_run
        self.__client = GooglePhotosClient(context.user_config_path)

    def configure(self) -> None:
        self.__client.configure()

    def can_handle(self, photo: Photo) -> bool:
        return photo.path.suffix.lower() in SUPPORTED_EXTENSIONS

    def process(self, photo: Photo) -> Optional[Dict[FactType, Any]]:
        if self.dry_run:
            photo.log(logging.INFO, "Uploaded to Google Photos")
            self.context.tally.increment(TALLY_KEY)
            return None

        if not self.__client.service:
            raise ProcessorSetupError(
                "Google Photos service not initialized. Skipping upload."
            )

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    upload_token = self.__client.upload_bytes(str(photo.path))

            response = self.__client.create_media_item(upload_token, photo.path.name)
            library_url = response["newMediaItemResults"][0]["mediaItem"]["productUrl"]

            photo.log(logging.INFO, "Uploaded to Google Photos: %s", library_url)
            self.context.tally.increment(TALLY_KEY)
        except Exception:
            photo.log(logging.ERROR, "Failed to upload to Google Photos", exc_info=True)
            raise

        return None
