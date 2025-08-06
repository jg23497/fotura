# NOTE: To use this postprocessor, you must:
# 1. Create OAuth credentials for a desktop app in Google Cloud Console.
# 2. Download the client_secret.json and place it at .secrets/client_secret.json (or set GOOGLE_CREDENTIALS_FILE).
# 3. The first run will prompt for authentication and store a token at .secrets/token.pickle (or set GOOGLE_TOKEN_PICKLE_FILE).


from pathlib import Path
import logging
from photo_tidy.postprocessors.postprocessor import Postprocessor
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from photo_tidy.processors.processor_setup_error import ProcessorSetupError
from photo_tidy.reporting.uploaded_report_item import UploadedReportItem

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", ".secrets/client_secret.json")
TOKEN_PICKLE_FILE = os.getenv("GOOGLE_TOKEN_PICKLE_FILE", ".secrets/token.pickle")


def get_google_photos_service():
    """
    See https://ai.google.dev/palm_docs/oauth_quickstart#2_write_the_credential_manager
    """
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("photoslibrary", "v1", credentials=creds, static_discovery=False)


class GooglePhotosUploadPostprocessor(Postprocessor):
    def __init__(self, report, dry_run: bool = False):
        self.report = report
        self.dry_run = dry_run
        self.service = None

    def set_up(self) -> None:
        try:
            self.service = get_google_photos_service()
        except Exception as e:
            logger.error(f"Failed to set up {self.__class__.__name__}: {e}")
            raise ProcessorSetupError(
                f"Missing secrets file for {self.__class__.__name__}", e
            )

    def can_handle(self, image_path: Path) -> bool:
        return image_path.suffix.lower() in {".jpg", ".jpeg", ".png"}

    def process(self, image_path: Path) -> None:
        if self.dry_run:
            logger.info(f"[DRY RUN] Would upload {image_path} to Google Photos API")
            return
        if not self.service:
            logger.error("Google Photos service not initialized. Skipping upload.")
            return
        try:
            # Step 1: Upload bytes to get upload token
            upload_token = self._upload_bytes(str(image_path))
            if not upload_token:
                logger.error(f"Failed to upload bytes for {image_path}")
                return
            # Step 2: Create media item using upload token
            response = self._create_media_item(upload_token, image_path.name)
            product_url = response["newMediaItemResults"][0]["mediaItem"]["productUrl"]
            logger.info(f"Uploaded {image_path} to Google Photos: {product_url}")
            self.report.log(UploadedReportItem(image_path, product_url))
        except Exception as e:
            logger.error(f"Error uploading {image_path} to Google Photos: {e}")

    def _upload_bytes(self, file_path: str) -> str | None:
        import requests

        creds = self.service._http.credentials
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": "image/jpeg",  # TODO: detect MIME type
            "X-Goog-Upload-Protocol": "raw",
        }
        with open(file_path, "rb") as f:
            data = f.read()
        response = requests.post(
            "https://photoslibrary.googleapis.com/v1/uploads",
            headers=headers,
            data=data,
        )
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Upload bytes failed: {response.status_code} {response.text}")
            return None

    def _create_media_item(self, upload_token: str, filename: str):
        body = {
            "newMediaItems": [
                {
                    "simpleMediaItem": {
                        "fileName": filename,
                        "uploadToken": upload_token,
                    },
                }
            ]
        }
        return self.service.mediaItems().batchCreate(body=body).execute()
