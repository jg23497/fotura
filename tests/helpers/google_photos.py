import contextlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import responses
from google.oauth2.credentials import Credentials


def create_client_secret():
    return {
        "installed": {
            "client_id": "foobar.apps.googleusercontent.com",
            "project_id": "foo",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "secret",
            "redirect_uris": ["http://localhost"],
        }
    }


def create_credentials(expiry=None, refresh_token="refresh-token"):
    if expiry is None:
        expiry = datetime.now() + timedelta(days=1)

    return Credentials(
        token="ya29.valid-token",
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/photoslibrary.appendonly"],
        expiry=expiry,
    )


def write_secret(secrets_dir, client_secret):
    secrets_subdir = secrets_dir / "integrations" / "google_photos"
    os.makedirs(secrets_subdir, exist_ok=True)

    with open(secrets_subdir / "client_secret.json", "w") as f:
        json.dump(client_secret, f)


def write_token(secrets_dir, creds):
    secrets_subdir = secrets_dir / "integrations" / "google_photos"
    os.makedirs(secrets_subdir, exist_ok=True)
    creds_path = secrets_subdir / "token.json"

    with open(creds_path, "w") as f:
        f.write(creds.to_json())

    return creds_path


def read_token():
    creds_path = Path(".secrets/integrations/google_photos/token.json")

    with open(creds_path, "r") as f:
        return Credentials.from_authorized_user_info(json.load(f))


@contextlib.contextmanager
def mock_installed_app_flow(flow):
    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
    ) as mock:
        mock.return_value = flow
        yield mock


def mock_successful_upload_response(count=1):
    for i in range(count):
        responses.add(
            responses.POST,
            "https://photoslibrary.googleapis.com/v1/uploads",
            body=f"upload-token-{i}",
            status=200,
            content_type="text/plain",
        )


def mock_failed_upload_response():
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        json={"error": {"message": "Upload failed"}},
        status=400,
    )


def mock_failed_upload_responses(count=1):
    for _ in range(count):
        mock_failed_upload_response()
