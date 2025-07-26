import pickle

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import responses
import json

from google.oauth2.credentials import Credentials

from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from photo_tidy.reporting.report import Report


def _create_google_oauth_2_client_secret_file_content():
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


@pytest.fixture
def google_oauth_2_client_secret():
    return _create_google_oauth_2_client_secret_file_content()


def _create_google_oauth_credentials(expiry):
    return Credentials(
        token="ya29.valid-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/photoslibrary.appendonly"],
        expiry=expiry,
    )


@pytest.fixture
def google_oauth_credentials_expired():
    return _create_google_oauth_credentials(
        expiry=(datetime.now() - timedelta(days=1)),
    )


@pytest.fixture
def google_oauth_credentials_fresh():
    return _create_google_oauth_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
    )


@pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".txt.jpg"])
def test_can_handle_returns_true_when_file_extension_is_in_supported_list(extension):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)
    assert processor.can_handle(Path(f"foo{extension}")), (
        f"Should handle extension: {extension}"
    )


@pytest.mark.parametrize("extension", [None, "", ".txt", ".mp4"])
def test_can_handle_returns_false_when_file_extension_is_not_supported(extension):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)
    assert not processor.can_handle(Path(f"Foo{extension}")), (
        f"Should not handle extension: {extension}"
    )


@responses.activate
def test_pickled_credentials_are_reused(fs, google_oauth_credentials_fresh):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)

    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)

    creds_path = secrets_dir / "token.pickle"
    with open(creds_path, "wb") as f:
        pickle.dump(google_oauth_credentials_fresh, f)

    processor.set_up()

    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


def test_sources_credentials_from_client_secret_file_when_pickled_credentials_not_found():
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)
    # TODO


@responses.activate
def test_refreshes_pickled_credentials_when_credentials_have_expired(
    fs, google_oauth_credentials_expired, google_oauth_2_client_secret
):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)

    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "ya29.new-token", "expires_in": 3600},
        status=200,
    )

    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)

    creds_path = secrets_dir / "token.pickle"
    with open(creds_path, "wb") as f:
        pickle.dump(google_oauth_credentials_expired, f)

    secret_path = secrets_dir / "client_secret.json"
    with open(secret_path, "w") as f:
        json.dump(google_oauth_2_client_secret, f)

    processor.set_up()

    creds_path = Path(".secrets/token.pickle")
    with open(creds_path, "rb") as f:
        credentials = pickle.load(f)

    assert "ya29.new-token" in credentials.token

    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")
