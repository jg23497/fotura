import pickle

import pytest
from pathlib import Path
import responses

from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from photo_tidy.reporting.report import Report


@pytest.fixture
def google_oauth_credentials():
    from google.oauth2.credentials import Credentials

    return Credentials(
        token="ya29.valid-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/photoslibrary.appendonly"],
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
def test_pickled_credentials_are_reused(fs, google_oauth_credentials):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)

    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "ya29.new-token", "expires_in": 3600},
        status=200,
    )

    secrets_dir = Path("/fake/.secrets")
    fs.create_dir(secrets_dir)

    creds_path = secrets_dir / "token.pickle"
    with open(creds_path, "wb") as f:
        pickle.dump(google_oauth_credentials, f)

    real_path = ".secrets/token.pickle"
    fs.create_symlink(real_path, creds_path)

    processor.set_up()

    service = processor.service

    assert service is not None
    assert hasattr(service, "mediaItems")
