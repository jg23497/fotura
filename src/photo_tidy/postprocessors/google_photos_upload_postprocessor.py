# NOTE: To use this postprocessor, you must:
# 1. Create OAuth credentials for a desktop app in Google Cloud Console.
# 2. Download the client_secret.json and place it at .secrets/client_secret.json (or set GOOGLE_CREDENTIALS_FILE).
# 3. The first run will prompt for authentication and store a token at .secrets/token.json (or set GOOGLE_TOKEN_FILE).


from pathlib import Path
import requests
import logging
from typing import Optional, Any
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from photo_tidy.postprocessors.postprocessor import Postprocessor
from photo_tidy.reporting.report import Report
from photo_tidy.processors.processor_setup_error import ProcessorSetupError
from photo_tidy.reporting.uploaded_report_item import UploadedReportItem

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", ".secrets/client_secret.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", ".secrets/token.json")


class GooglePhotosUploadPostprocessor(Postprocessor):
    def __init__(self, report: Report, dry_run: bool = False) -> None:
        self.report = report
        self.dry_run = dry_run
        self.service = None

    def set_up(self) -> None:
        credentials = self._obtain_credentials()
        self.service = build(
            "photoslibrary", "v1", credentials=credentials, static_discovery=False
        )

    def _load_cached_credentials(self, token_file_path: str) -> Optional[Credentials]:
        try:
            return Credentials.from_authorized_user_file(token_file_path, SCOPES)
        except (ValueError, OSError):
            # Invalid or corrupted credentials file. Let's start start a new OAuth flow.
            return None

    def _initiate_oauth_flow(self, credentials_file_path: str) -> Credentials:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file_path, SCOPES
            )
            return flow.run_local_server(port=0)
        except FileNotFoundError as e:
            raise ProcessorSetupError(
                f"Google credentials file not found at {credentials_file_path}.", e
            )

    def _save_credentials(self, credentials: Credentials) -> None:
        with open(TOKEN_FILE, "w") as token:
            token.write(credentials.to_json())

    def _obtain_credentials(self) -> Optional[Credentials]:
        """
        Obtain and manage Google OAuth credentials for the Google Photos API.

        This method implements a complete OAuth 2.0 credential lifecycle:
        1. First attempts to load cached credentials from the token file
        2. If cached credentials exist but are expired, attempts to refresh them
        3. If no valid credentials exist, initiates a new OAuth flow
        4. Saves the credentials for future use

        Returns:
            Credentials: Valid Google OAuth credentials for Photos API access

        Raises:
            ProcessorSetupError: If the credentials file is not found during
                               OAuth flow initiation
        """
        credentials = None

        if os.path.exists(TOKEN_FILE):
            credentials = self._load_cached_credentials(TOKEN_FILE)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                credentials = self._initiate_oauth_flow(CREDENTIALS_FILE)
            self._save_credentials(credentials)

        return credentials

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

    def _upload_bytes(self, file_path: str) -> Optional[str]:
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

    def _create_media_item(self, upload_token: str, filename: str) -> dict[str, Any]:
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
