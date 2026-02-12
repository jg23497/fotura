import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from fotura.processors.processor_setup_error import ProcessorSetupError

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]
TALLY_KEY = "uploaded to google photos"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class GooglePhotosClient:
    def __init__(self, user_config_path: Path) -> None:
        self.__user_config_path = user_config_path
        self.service = None

    def configure(self) -> None:
        """Initialize the Google Photos service with valid credentials."""
        credentials = self.__obtain_credentials()
        self.service = build(
            "photoslibrary",
            "v1",
            credentials=credentials,
            static_discovery=False,
            cache_discovery=False,
        )

    def upload_bytes(self, file_path: str) -> str:
        """
        Upload image bytes to Google Photos.

        Returns an upload token that can be used with batchCreate.
        Raises RuntimeError if the upload fails.
        """
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
            f"Upload request to Photos Library API failed: "
            f"{response.status_code} {response.text}"
        )

    def create_media_item(self, upload_token: str, filename: str) -> Dict[str, Any]:
        """
        Create a media item in Google Photos from an upload token.

        Returns the API response containing newMediaItemResults.
        """
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

    def batch_create_media_items(self, items: list[tuple[str, str]]) -> Dict[str, Any]:
        """
        Create multiple media items in a single API call.

        Args:
            items: List of (filename, upload_token) tuples

        Returns the API response containing newMediaItemResults.
        """
        body = {
            "newMediaItems": [
                {
                    "simpleMediaItem": {
                        "fileName": filename,
                        "uploadToken": token,
                    }
                }
                for filename, token in items
            ]
        }
        return self.service.mediaItems().batchCreate(body=body).execute()

    def __get_file_upload_headers(self, file_path: str) -> Dict[str, str]:
        credentials = self.service._http.credentials
        mime_type, _ = mimetypes.guess_type(file_path)
        return {
            "Authorization": f"Bearer {credentials.token}",
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": mime_type or "application/octet-stream",
            "X-Goog-Upload-Protocol": "raw",
        }

    def __get_credentials_directory_path(self) -> Path:
        path = self.__user_config_path / "integrations" / "google_photos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def __get_credentials_file_path(self) -> Path:
        return self.__get_credentials_directory_path() / "client_secret.json"

    def __get_token_file_path(self) -> Path:
        return self.__get_credentials_directory_path() / "token.json"

    def __load_cached_credentials(self) -> Optional[Credentials]:
        token_file_path = self.__get_token_file_path()

        if not os.path.exists(token_file_path):
            return None

        try:
            return Credentials.from_authorized_user_file(str(token_file_path), SCOPES)
        except (ValueError, OSError):
            return None

    def __save_credentials(self, credentials: Credentials) -> None:
        with open(self.__get_token_file_path(), "w") as token:
            token.write(credentials.to_json())

    def __initiate_oauth_flow(self) -> Credentials:
        credentials_file_path = self.__get_credentials_file_path()
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file_path), SCOPES
            )
            return flow.run_local_server(port=0)
        except FileNotFoundError as e:
            raise ProcessorSetupError(
                f"Google credentials file not found at {credentials_file_path}.", e
            )

    def __refresh_credentials_or_initiate_oauth(
        self, credentials: Credentials
    ) -> Credentials:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                return credentials
            except RefreshError:
                pass
        return self.__initiate_oauth_flow()

    def __obtain_credentials(self) -> Credentials:
        """Obtain and manage Google OAuth credentials for the Google Photos API."""
        credentials = self.__load_cached_credentials()

        if not credentials or not credentials.valid:
            credentials = self.__refresh_credentials_or_initiate_oauth(credentials)
            self.__save_credentials(credentials)

        return credentials
