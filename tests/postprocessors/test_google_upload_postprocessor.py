import os
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
    TOKEN_FILE,
)

# Test helper methods


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


def create_credentials(expiry, refresh_token="refresh-token"):
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
    secret_path = secrets_dir / "client_secret.json"
    with open(secret_path, "w") as f:
        json.dump(client_secret, f)


def write_token(secrets_dir, creds):
    creds_path = secrets_dir / "token.json"
    with open(creds_path, "w") as f:
        f.write(creds.to_json())
    return creds_path


def read_token():
    creds_path = Path(".secrets/token.json")
    with open(creds_path, "r") as f:
        return Credentials.from_authorized_user_info(json.load(f))


@contextlib.contextmanager
def mock_installed_app_flow(flow):
    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
    ) as mock:
        mock.return_value = flow
        yield mock


# Fixtures


@pytest.fixture
def client_secret():
    return create_client_secret()


@pytest.fixture
def creds_expired():
    return create_credentials(expiry=datetime.now() - timedelta(days=1))


@pytest.fixture
def creds_fresh():
    return create_credentials(expiry=datetime.now() + timedelta(days=1))


@pytest.fixture
def secrets_dir(fs):
    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)
    return secrets_dir


@pytest.fixture
def processor():
    report = Report()
    return GooglePhotosUploadPostprocessor(report)


# Tests


@pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png", ".txt.jpg"])
def test_handles_supported_extensions(ext, processor):
    assert processor.can_handle(Path(f"foo{ext}"))


@pytest.mark.parametrize("ext", [None, "", ".txt", ".mp4"])
def test_rejects_unsupported_extensions(ext, processor):
    assert not processor.can_handle(Path(f"foo{ext}"))


def test_uses_oauth_flow_if_no_cached_credentials_found(
    secrets_dir, creds_fresh, processor
):
    assert not os.path.exists(TOKEN_FILE)

    flow = Mock()
    flow.run_local_server.return_value = creds_fresh

    with mock_installed_app_flow(flow):
        processor.set_up()

        assert os.path.exists(TOKEN_FILE)
        assert processor.service is not None, "Processor service should be initialized"


def test_reuses_valid_cached_token(secrets_dir, creds_fresh, processor):
    write_token(secrets_dir, creds_fresh)

    processor.set_up()

    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


@responses.activate
def test_refreshes_expired_credentials_if_token_has_expired_and_refresh_token_is_present(
    secrets_dir, creds_expired, client_secret, processor
):
    write_token(secrets_dir, creds_expired)
    write_secret(secrets_dir, client_secret)

    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "ya29.new-token", "expires_in": 3600},
        status=200,
    )

    processor.set_up()

    credentials = read_token()
    assert "ya29.new-token" in credentials.token
    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


def test_oauth_flow_if_token_has_expired_and_no_refresh_is_present(
    secrets_dir, processor
):
    expired_creds = create_credentials(
        expiry=(datetime.now() - timedelta(days=1)),
        refresh_token=None,
    )
    write_token(secrets_dir, expired_creds)
    assert os.path.exists(TOKEN_FILE)

    flow = Mock()
    flow.run_local_server.return_value = create_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )

    with mock_installed_app_flow(flow):
        processor.set_up()

        assert os.path.exists(TOKEN_FILE)
        assert processor.service is not None, "Processor service should be initialized"
