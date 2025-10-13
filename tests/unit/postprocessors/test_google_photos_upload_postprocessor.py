import os
import pytest
import responses
import json
import contextlib

from unittest.mock import MagicMock, Mock, patch
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from photo_tidy.processors.context import Context
from photo_tidy.processors.processor_setup_error import ProcessorSetupError
from photo_tidy.reporting.report import Report
from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
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
    secrets_subdir = secrets_dir / "integrations" / "google_photos"
    os.makedirs(secrets_subdir, exist_ok=True)
    secret_path = secrets_subdir / "client_secret.json"
    with open(secret_path, "w") as f:
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


@contextlib.contextmanager
def mock_successful_media_item_creation(processor):
    with patch.object(processor.service, "mediaItems") as mock_media_items:
        mock_batch_create = Mock()
        mock_batch_create.return_value.execute.return_value = {
            "newMediaItemResults": [
                {
                    "mediaItem": {
                        "productUrl": "https://photos.google.com/photo/AF1QipM_12345"
                    }
                }
            ]
        }
        mock_media_items.return_value.batchCreate = mock_batch_create
        yield mock_batch_create


def mock_successful_upload_response():
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        body="upload-token-12345",
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


# Fixtures


@pytest.fixture(autouse=True)
def mock_photoslibrary_service():
    with patch(
        "photo_tidy.postprocessors.google_photos_upload_postprocessor.build"
    ) as mock_build:
        mock_service = MagicMock()
        mock_service._http = MagicMock(
            credentials=MagicMock(token="ya29.default-token")
        )
        mock_build.return_value = mock_service
        yield mock_build


@pytest.fixture
def client_secret():
    return create_client_secret()


@pytest.fixture
def cached_credentials_expired():
    return create_credentials(expiry=datetime.now() - timedelta(days=1))


@pytest.fixture
def cached_credentials_valid():
    return create_credentials(expiry=datetime.now() + timedelta(days=1))


@pytest.fixture
def secrets_dir(fs):
    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)
    return secrets_dir


@pytest.fixture
def processor(secrets_dir):
    report = Report()
    context = Context(report=report, user_config_path=secrets_dir, dry_run=False)
    return GooglePhotosUploadPostprocessor(context)


@pytest.fixture
def processor_dry_run(secrets_dir):
    report = Report()
    context = Context(report=report, user_config_path=secrets_dir, dry_run=True)
    return GooglePhotosUploadPostprocessor(context)


@pytest.fixture
def processor_with_valid_credentials(secrets_dir, cached_credentials_valid, processor):
    write_token(secrets_dir, cached_credentials_valid)
    processor.configure()
    return processor


@pytest.fixture
def test_image_file(fs):
    test_image_path = Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"fake image data")
    return test_image_path


@pytest.fixture
def test_image_file_png(fs):
    test_image_path = Path("test_image.png")
    fs.create_file(test_image_path, contents=b"fake image data")
    return test_image_path


# Tests

## can_handle method


@pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png", ".txt.jpg"])
def test_handles_supported_extensions(ext, processor):
    assert processor.can_handle(Path(f"foo{ext}"))


@pytest.mark.parametrize("ext", [None, "", ".txt", ".mp4"])
def test_rejects_unsupported_extensions(ext, processor):
    assert not processor.can_handle(Path(f"foo{ext}"))


## configure method


def test_uses_oauth_flow_and_caches_credentials_if_no_cached_credentials_exist(
    secrets_dir, cached_credentials_valid, processor
):
    assert not os.path.exists(
        secrets_dir / "integrations" / "google_photos" / "token.json"
    )

    flow = Mock()
    flow.run_local_server.return_value = cached_credentials_valid

    with mock_installed_app_flow(flow):
        processor.configure()

        assert processor.service is not None, "Processor service should be initialized"
        credentials = read_token()
        assert "ya29.valid-token" in credentials.token


def test_raises_error_if_no_cached_credentials_exist_and_client_secret_is_not_found(
    secrets_dir, processor
):
    assert not os.path.exists(
        secrets_dir / "integrations" / "google_photos" / "client_secret.json"
    )
    assert not os.path.exists(
        secrets_dir / "integrations" / "google_photos" / "token.json"
    )

    with pytest.raises(
        ProcessorSetupError, match=r"Google credentials file not found at.*"
    ):
        processor.configure()


def test_reuses_valid_cached_token(secrets_dir, cached_credentials_valid, processor):
    write_token(secrets_dir, cached_credentials_valid)

    processor.configure()

    service = processor.service
    assert service is not None
    assert hasattr(service, "mediaItems")


@responses.activate
def test_refreshes_cached_credentials_if_token_has_expired_and_refresh_token_is_present(
    secrets_dir, cached_credentials_expired, client_secret, processor
):
    write_token(secrets_dir, cached_credentials_expired)
    write_secret(secrets_dir, client_secret)

    responses.add(
        responses.POST,
        "https://oauth2.googleapis.com/token",
        json={"access_token": "ya29.new-token", "expires_in": 3600},
        status=200,
    )

    processor.configure()

    service = processor.service
    assert service is not None

    credentials = read_token()
    assert "ya29.new-token" in credentials.token


def test_uses_oauth_flow_if_token_has_expired_and_no_refresh_token_is_present(
    secrets_dir, processor
):
    expired_credentials = create_credentials(
        expiry=(datetime.now() - timedelta(days=1)),
        refresh_token="",
    )
    write_token(secrets_dir, expired_credentials)
    assert os.path.exists(secrets_dir / "integrations" / "google_photos" / "token.json")

    flow = Mock()
    flow.run_local_server.return_value = create_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )

    with mock_installed_app_flow(flow):
        processor.configure()

        credentials = read_token()
        assert "ya29.valid-token" in credentials.token
        assert "refresh-token" in credentials.refresh_token
        assert processor.service is not None, "Processor service should be initialized"


def test_uses_oauth_flow_if_token_has_expired_and_refresh_token_is_present_but_expired(
    secrets_dir, processor
):
    expired_credentials = create_credentials(
        expiry=(datetime.now() - timedelta(days=1)),
        refresh_token="123",
    )
    write_token(secrets_dir, expired_credentials)
    assert os.path.exists(secrets_dir / "integrations" / "google_photos" / "token.json")

    flow = Mock()
    flow.run_local_server.return_value = create_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )

    with patch(
        "google.oauth2.credentials.Credentials.refresh", side_effect=RefreshError()
    ):
        with mock_installed_app_flow(flow):
            processor.configure()

            credentials = read_token()
            assert "ya29.valid-token" in credentials.token
            assert "refresh-token" in credentials.refresh_token
            assert processor.service is not None, (
                "Processor service should be initialized"
            )


## process method


@responses.activate
def test_process_uploads_image_bytes_to_google_photos_uploads_api(
    processor_with_valid_credentials, test_image_file
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(test_image_file)

        assert len(responses.calls) == 1
        upload_call = responses.calls[0]
        assert upload_call.request is not None
        assert (
            upload_call.request.url == "https://photoslibrary.googleapis.com/v1/uploads"
        )
        assert upload_call.request.headers is not None
        assert (
            upload_call.request.headers["Authorization"] == "Bearer ya29.default-token"
        )
        assert upload_call.request.headers["Content-type"] == "application/octet-stream"
        assert upload_call.request.headers["X-Goog-Upload-Content-Type"] == "image/jpeg"
        assert upload_call.request.headers["X-Goog-Upload-Protocol"] == "raw"
        assert upload_call.request.body == b"fake image data"


@pytest.mark.parametrize(
    "image_fixture,expected_mime_type",
    [
        ("test_image_file_png", "image/png"),
        ("test_image_file", "image/jpeg"),
    ],
)
@responses.activate
def test_process_specifies_correct_image_mimetype_in_uploads_api_request(
    processor_with_valid_credentials, image_fixture, expected_mime_type, request
):
    mock_successful_upload_response()
    image_path = request.getfixturevalue(image_fixture)

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(image_path)

        upload_call = responses.calls[0]
        assert upload_call.request.headers is not None
        assert (
            upload_call.request.headers.get("X-Goog-Upload-Content-Type")
            == expected_mime_type
        )


@responses.activate
def test_successful_upload_process_creates_media_item_with_upload_token(
    processor_with_valid_credentials, test_image_file
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(
        processor_with_valid_credentials
    ) as mock_batch_create:
        processor_with_valid_credentials.process(test_image_file)

        assert mock_batch_create.call_count == 1
        called_body = mock_batch_create.call_args.kwargs["body"]
        assert called_body == {
            "newMediaItems": [
                {
                    "simpleMediaItem": {
                        "fileName": test_image_file.name,
                        "uploadToken": "upload-token-12345",
                    }
                }
            ]
        }


@responses.activate
def test_successful_upload_process_logs_uploaded_report_item(
    processor_with_valid_credentials, test_image_file
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(test_image_file)

        report_items = processor_with_valid_credentials.report.get_report()
        uploaded_items = [item for item in report_items if item.name() == "Uploaded"]
        assert len(uploaded_items) == 1
        assert uploaded_items[0].source == str(test_image_file)
        assert (
            uploaded_items[0].destination
            == "https://photos.google.com/photo/AF1QipM_12345"
        )


@responses.activate
def test_process_raises_exception_and_skips_upload_when_image_bytes_upload_fails(
    processor_with_valid_credentials, test_image_file
):
    mock_failed_upload_response()

    with pytest.raises(RuntimeError):
        with mock_successful_media_item_creation(
            processor_with_valid_credentials
        ) as createMediaItemMock:
            processor_with_valid_credentials.process(test_image_file)

            assert len(responses.calls) == 1
            assert createMediaItemMock.call_count == 0


@responses.activate
def test_process_raises_exception_and_skips_upload_when_service_not_initialized(
    processor, test_image_file
):
    processor.service = None

    with pytest.raises(ProcessorSetupError):
        processor.process(test_image_file)

        assert len(responses.calls) == 0


@responses.activate
def test_process_logs_failed_upload_report_item_when_service_not_initialized(
    processor, test_image_file
):
    processor.service = None

    with pytest.raises(ProcessorSetupError):
        processor.process(test_image_file)

        report_items = processor.report.get_report()
        failed_upload_items = [
            item for item in report_items if item.name() == "Failed Upload"
        ]
        assert len(failed_upload_items) == 1
        assert failed_upload_items[0].source == str(test_image_file)
        assert "Google Photos service not initialized" in str(
            failed_upload_items[0].exception
        )


@responses.activate
def test_process_skips_upload_when_dry_run_enabled(processor_dry_run, test_image_file):
    processor_dry_run.process(test_image_file)

    assert len(responses.calls) == 0


def test_process_logs_dry_run_uploaded_message_when_dry_run_enabled(
    processor_dry_run, test_image_file
):
    processor_dry_run.process(test_image_file)

    report_items = processor_dry_run.report.get_report()
    uploaded_items = [item for item in report_items if item.name() == "Uploaded"]
    assert len(uploaded_items) == 1
    assert uploaded_items[0].source == str(test_image_file)
    assert uploaded_items[0].destination == "Google Photos"


@responses.activate
def test_process_logs_failed_upload_exception_if_exception_occurs(
    processor, secrets_dir, cached_credentials_valid, test_image_file
):
    write_token(secrets_dir, cached_credentials_valid)
    processor.configure()

    mock_http = Mock()
    mock_http.credentials = cached_credentials_valid

    def mock_request_that_fails():
        raise Exception("API Error")

    mock_http.request = mock_request_that_fails
    assert processor.service is not None
    processor.service._http = mock_http

    mock_successful_upload_response()

    with pytest.raises(Exception):
        processor.process(test_image_file)

        assert len(responses.calls) == 1

        report_items = processor.report.get_report()
        failed_report_items = [
            item for item in report_items if item.name() == "Failed Upload"
        ]
        assert len(failed_report_items) == 1
