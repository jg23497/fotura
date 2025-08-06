import os
import pickle
import pytest
import responses
import json
import contextlib

from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials

from photo_tidy.reporting.report import Report
from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
    TOKEN_PICKLE_FILE,
)


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


def _create_google_oauth_credentials(expiry, refresh_token="refresh-token"):
    return Credentials(
        token="ya29.valid-token",
        refresh_token=refresh_token,
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
        refresh_token="refresh-token",
    )


@pytest.fixture
def google_oauth_credentials_fresh():
    return _create_google_oauth_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )


@pytest.fixture
def secrets_dir_fs(fs):
    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)
    return secrets_dir


@pytest.fixture
def processor():
    report = Report()
    return GooglePhotosUploadPostprocessor(report)


@contextlib.contextmanager
def mock_installed_app_flow(flow):
    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
    ) as mock_from_client_secrets_file:
        mock_from_client_secrets_file.return_value = flow
        yield mock_from_client_secrets_file


def write_pickled_credentials(secrets_dir, credentials):
    creds_path = secrets_dir / "token.pickle"
    with open(creds_path, "wb") as f:
        pickle.dump(credentials, f)
    return creds_path


def read_pickled_credentials():
    creds_path = Path(".secrets/token.pickle")
    with open(creds_path, "rb") as f:
        return pickle.load(f)


@pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".txt.jpg"])
def test_can_handle_returns_true_when_file_extension_is_in_supported_list(
    extension, processor
):
    assert processor.can_handle(Path(f"foo{extension}")), (
        f"Should handle extension: {extension}"
    )


@pytest.mark.parametrize("extension", [None, "", ".txt", ".mp4"])
def test_can_handle_returns_false_when_file_extension_is_not_supported(
    extension, processor
):
    assert not processor.can_handle(Path(f"Foo{extension}")), (
        f"Should not handle extension: {extension}"
    )


def test_initiates_oauth_flow_when_pickled_credentials_are_not_present(
    secrets_dir_fs, google_oauth_credentials_fresh, processor
):
    assert not os.path.exists(TOKEN_PICKLE_FILE)

    flow = Mock()
    flow.run_local_server.return_value = google_oauth_credentials_fresh

    with mock_installed_app_flow(flow):
        processor.set_up()

        assert os.path.exists(TOKEN_PICKLE_FILE)
        assert processor.service is not None, "Processor service should be initialized"


def test_pickled_credentials_are_reused_when_present_and_valid(
    secrets_dir_fs, google_oauth_credentials_fresh, processor
):
    write_pickled_credentials(secrets_dir_fs, google_oauth_credentials_fresh)

    processor.set_up()

    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


@responses.activate
def test_refreshes_pickled_credentials_when_pickled_credentials_are_present_but_have_expired(
    secrets_dir_fs,
    google_oauth_credentials_expired,
    google_oauth_2_client_secret,
    processor,
):
    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "ya29.new-token", "expires_in": 3600},
        status=200,
    )
    write_pickled_credentials(secrets_dir_fs, google_oauth_credentials_expired)
    secret_path = secrets_dir_fs / "client_secret.json"
    with open(secret_path, "w") as f:
        json.dump(google_oauth_2_client_secret, f)

    processor.set_up()

    credentials = read_pickled_credentials()
    assert "ya29.new-token" in credentials.token
    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


def test_triggers_oauth_flow_when_credentials_have_expired_and_no_refresh_token_is_available(
    secrets_dir_fs, processor
):
    expired_creds = _create_google_oauth_credentials(
        expiry=(datetime.now() - timedelta(days=1)),
        refresh_token=None,
    )
    write_pickled_credentials(secrets_dir_fs, expired_creds)
    assert os.path.exists(TOKEN_PICKLE_FILE)

    flow = Mock()
    flow.run_local_server.return_value = _create_google_oauth_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )

    with mock_installed_app_flow(flow):
        processor.set_up()

        assert os.path.exists(TOKEN_PICKLE_FILE)
        assert processor.service is not None, "Processor service should be initialized"
