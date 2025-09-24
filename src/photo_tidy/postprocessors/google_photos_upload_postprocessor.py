from pathlib import Path
import requests
import logging
import mimetypes
from typing import Optional, Any
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

from photo_tidy.postprocessors.postprocessor import Postprocessor
from photo_tidy.reporting.failed_upload_report_item import FailedUploadReportItem
from photo_tidy.reporting.report import Report
from photo_tidy.processors.processor_setup_error import ProcessorSetupError
from photo_tidy.reporting.uploaded_report_item import UploadedReportItem

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", ".secrets/client_secret.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", ".secrets/token.json")


class GooglePhotosUploadPostprocessor(Postprocessor):
    def __init__(self, report: Report, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.report = report
        self.service = None

    def set_up(self) -> None:
        credentials = self.__obtain_credentials()
        self.service = build(
            "photoslibrary", "v1", credentials=credentials, static_discovery=False
        )

    def can_handle(self, image_path: Path) -> bool:
        return image_path.suffix.lower() in {".jpg", ".jpeg", ".png"}

    def process(self, image_path: Path) -> None:
        if self.dry_run:
            self.report.log(UploadedReportItem(image_path, "Google Photos"))
            return
        try:
            if not self.service:
                raise ProcessorSetupError(
                    "Google Photos service not initialized. Skipping upload."
                )

            upload_token = self.__upload_bytes(str(image_path))
            response = self.__create_media_item(upload_token, image_path.name)
            library_url = response["newMediaItemResults"][0]["mediaItem"]["productUrl"]
            self.report.log(UploadedReportItem(image_path, library_url))
        except Exception as e:
            self.report.log(FailedUploadReportItem(image_path, e))
            raise

    def __upload_bytes(self, file_path: str) -> Optional[str]:
        headers = self.__get_file_upload_headers(file_path)
        with open(file_path, "rb") as f:
            data = f.read()
        response = requests.post(
            "https://photoslibrary.googleapis.com/v1/uploads",
            headers=headers,
            data=data,
        )
        if response.status_code == 200:
            return response.text
        raise RuntimeError(
            f"Upload request to Photos Library API failed: {response.status_code} {response.text}"
        )

    def __get_file_upload_headers(self, file_path: str):
        credentials = self.service._http.credentials
        mime_type, _ = mimetypes.guess_type(file_path)
        return {
            "Authorization": f"Bearer {credentials.token}",
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime_type,
            "X-Goog-Upload-Protocol": "raw",
        }

    def __create_media_item(self, upload_token: str, filename: str) -> dict[str, Any]:
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

    def __load_cached_credentials(self, token_file_path: str) -> Optional[Credentials]:
        if not os.path.exists(TOKEN_FILE):
            return None
        try:
            return Credentials.from_authorized_user_file(token_file_path, SCOPES)
        except (ValueError, OSError):
            return None

    def __save_credentials(self, credentials: Credentials) -> None:
        with open(TOKEN_FILE, "w") as token:
            token.write(credentials.to_json())

    def __initiate_oauth_flow(self, credentials_file_path: str) -> Credentials:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file_path, SCOPES
            )
            return flow.run_local_server(port=0)
        except FileNotFoundError as e:
            raise ProcessorSetupError(
                f"Google credentials file not found at {credentials_file_path}.", e
            )

    def __refresh_credentials_or_initiate_oauth(
        self, credentials: Credentials
    ) -> Optional[Credentials]:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                return credentials
            except RefreshError:
                # The refresh token has expired
                pass
        return self.__initiate_oauth_flow(CREDENTIALS_FILE)

    def __obtain_credentials(self) -> Optional[Credentials]:
        """
        Obtain and manage Google OAuth credentials for the Google Photos API.

        This method implements a complete OAuth 2.0 credential lifecycle:
        1. First attempts to load cached credentials from the token file
        2. If cached credentials exist but are expired, attempts to refresh them
        3. If no valid credentials exist or the refresh fails, initiates a new OAuth flow
        4. Saves the credentials for future use

        Returns:
            Credentials: Valid Google OAuth credentials for Photos API access

        Raises:
            ProcessorSetupError: If the credentials file is not found during
                               OAuth flow initiation
        """
        credentials = self.__load_cached_credentials(TOKEN_FILE)

        if not credentials or not credentials.valid:
            credentials = self.__refresh_credentials_or_initiate_oauth(credentials)
            self.__save_credentials(credentials)

        return credentials
