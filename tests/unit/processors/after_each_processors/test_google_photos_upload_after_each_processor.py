import contextlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import responses
from google.auth.exceptions import RefreshError

from fotura.domain.photo import Photo
from fotura.persistence.database import Database
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.persistence.upload_status import UploadStatus
from fotura.processors.after_each_processors.google_photos_upload_after_each_processor import (
    GooglePhotosUploadAfterEachProcessor,
)
from fotura.processors.context import Context
from fotura.processors.processor_setup_error import ProcessorSetupError
from tests.helpers.google_photos import (
    create_credentials,
    mock_failed_upload_response,
    mock_failed_upload_responses,
    mock_installed_app_flow,
    mock_successful_upload_response,
    read_token,
    write_secret,
    write_token,
)
from tests.helpers.helper import get_log_entries

# Test helper methods


@contextlib.contextmanager
def mock_successful_media_item_creation(processor):
    with patch.object(get_client_service(processor), "mediaItems") as mock_media_items:
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


def mock_failed_media_item_creation(processor):
    return patch.object(
        get_client_service(processor),
        "mediaItems",
        **{
            "return_value.batchCreate.return_value.execute.return_value": {
                "newMediaItemResults": [
                    {"status": {"message": "INVALID_ARGUMENT: Invalid upload token"}}
                ]
            }
        },
    )


def get_client_service(processor):
    return processor._GooglePhotosUploadAfterEachProcessor__uploader._client.service


# Fixtures


@pytest.fixture
def processor(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    return GooglePhotosUploadAfterEachProcessor(context)


@pytest.fixture
def processor_dry_run(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=True, database=Database()
    )
    return GooglePhotosUploadAfterEachProcessor(context)


@pytest.fixture
def processor_with_valid_credentials(secrets_dir, cached_credentials_valid, processor):
    write_token(secrets_dir, cached_credentials_valid)
    processor.configure()
    return processor


@pytest.fixture
def test_photo(fs):
    test_image_path = Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"fake image data")
    return Photo(test_image_path)


@pytest.fixture
def test_photo_png(fs):
    test_image_path = Path("test_image.png")
    fs.create_file(test_image_path, contents=b"fake image data")
    return Photo(test_image_path)


@pytest.fixture
def repository(processor_with_valid_credentials):
    return GooglePhotosUploadRepository(
        processor_with_valid_credentials.context.database
    )


# Tests

## can_handle method


@pytest.mark.parametrize(
    "ext",
    [
        ".avif",
        ".bmp",
        ".gif",
        ".heic",
        ".ico",
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
        ".txt.jpg",
    ],
)
def test_handles_supported_extensions(ext, processor, fs):
    path = Path(f"foo{ext}")
    fs.create_file(path, contents=b"data")
    assert processor.can_handle(Photo(path))


@pytest.mark.parametrize("ext", [None, "", ".txt", ".mp4"])
def test_rejects_unsupported_extensions(ext, processor, fs):
    path = Path(f"foo{ext}")
    fs.create_file(path, contents=b"data")
    assert not processor.can_handle(Photo(path))


def test_rejects_file_exceeding_max_file_size(processor, fs):
    path = Path("oversized.jpg")
    fs.create_file(path, st_size=200 * 1024 * 1024 + 1)
    assert not processor.can_handle(Photo(path))


def test_accepts_file_at_exactly_the_max_file_size(processor, fs):
    path = Path("exact.jpg")
    fs.create_file(path, st_size=200 * 1024 * 1024)
    assert processor.can_handle(Photo(path))


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

        assert get_client_service(processor) is not None, (
            "Processor service should be initialized"
        )
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

    service = get_client_service(processor)
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

    service = get_client_service(processor)
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
        assert get_client_service(processor) is not None, (
            "Processor service should be initialized"
        )


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
            assert get_client_service(processor) is not None, (
                "Processor service should be initialized"
            )


## process method


@responses.activate
def test_process_uploads_image_bytes_to_google_photos_uploads_api(
    processor_with_valid_credentials, test_photo
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(test_photo)

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
    "photo_fixture,expected_mime_type",
    [
        ("test_photo_png", "image/png"),
        ("test_photo", "image/jpeg"),
    ],
)
@responses.activate
def test_process_specifies_correct_image_mimetype_in_uploads_api_request(
    processor_with_valid_credentials, photo_fixture, expected_mime_type, request
):
    mock_successful_upload_response()
    photo = request.getfixturevalue(photo_fixture)

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(photo)

        upload_call = responses.calls[0]
        assert upload_call.request.headers is not None
        assert (
            upload_call.request.headers.get("X-Goog-Upload-Content-Type")
            == expected_mime_type
        )


@responses.activate
def test_successful_upload_process_creates_media_item_with_upload_token(
    processor_with_valid_credentials, test_photo
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(
        processor_with_valid_credentials
    ) as mock_batch_create:
        processor_with_valid_credentials.process(test_photo)

        assert mock_batch_create.call_count == 1
        called_body = mock_batch_create.call_args.kwargs["body"]
        assert called_body == {
            "newMediaItems": [
                {
                    "simpleMediaItem": {
                        "fileName": test_photo.path.name,
                        "uploadToken": "upload-token-0",
                    }
                }
            ]
        }


@responses.activate
def test_successful_upload_process_logs_uploaded_report_item(
    processor_with_valid_credentials, test_photo, caplog
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        with caplog.at_level(logging.INFO):
            processor_with_valid_credentials.process(test_photo)

        log_entries = get_log_entries(
            caplog,
            lambda r: (
                r.levelno == logging.INFO and r.getMessage().startswith("Uploaded")
            ),
        )

        assert len(log_entries) == 1
        assert (
            "https://photos.google.com/photo/AF1QipM_12345"
            in log_entries[0].getMessage()
        )


@responses.activate
def test_process_raises_exception_and_skips_upload_when_image_bytes_upload_fails(
    processor_with_valid_credentials, test_photo
):
    mock_failed_upload_response()

    with pytest.raises(RuntimeError):
        with mock_successful_media_item_creation(
            processor_with_valid_credentials
        ) as createMediaItemMock:
            with patch("time.sleep"):
                processor_with_valid_credentials.process(test_photo)

            assert len(responses.calls) == 1
            assert createMediaItemMock.call_count == 0


@responses.activate
def test_process_raises_exception_and_skips_upload_when_service_not_initialized(
    processor, test_photo
):
    with pytest.raises(ProcessorSetupError):
        processor.process(test_photo)

        assert len(responses.calls) == 0


@responses.activate
def test_process_logs_failed_upload_report_item_when_service_not_initialized(
    processor, test_photo
):
    with pytest.raises(ProcessorSetupError):
        processor.process(test_photo)

        report_items = processor.report.get_report()
        failed_upload_items = [
            item for item in report_items if item.name() == "Failed Upload"
        ]
        assert len(failed_upload_items) == 1
        assert failed_upload_items[0].source == str(test_photo)
        assert "Google Photos service not initialized" in str(
            failed_upload_items[0].exception
        )


@responses.activate
def test_process_skips_upload_when_dry_run_enabled(processor_dry_run, test_photo):
    processor_dry_run.process(test_photo)

    assert len(responses.calls) == 0


def test_process_logs_dry_run_uploaded_message_when_dry_run_enabled(
    processor_dry_run, test_photo, caplog
):
    with caplog.at_level(logging.INFO):
        processor_dry_run.process(test_photo)

    log_entries = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.INFO and r.getMessage().startswith("Uploaded"),
    )

    assert len(log_entries) == 1


def test_process_increments_tally_when_dry_run_enabled(
    processor_dry_run, test_photo, tally
):
    processor_dry_run.process(test_photo)

    final_snapshot = tally.get_snapshot()
    assert final_snapshot.get("uploaded to google photos") == 1


@responses.activate
def test_process_increments_tally_when_uploaded_successfully(
    processor_with_valid_credentials, test_photo, tally
):
    mock_successful_upload_response()
    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(test_photo)

    final_snapshot = tally.get_snapshot()
    assert final_snapshot.get("uploaded to google photos") == 1


@responses.activate
def test_process_logs_failed_upload_exception_if_exception_occurs(
    processor, secrets_dir, cached_credentials_valid, test_photo
):
    write_token(secrets_dir, cached_credentials_valid)
    processor.configure()

    mock_http = Mock()
    mock_http.credentials = cached_credentials_valid

    def mock_request_that_fails():
        raise Exception("API Error")

    mock_http.request = mock_request_that_fails
    assert get_client_service(processor) is not None
    get_client_service(processor)._http = mock_http

    mock_successful_upload_response()

    with pytest.raises(Exception):
        processor.process(test_photo)

        assert len(responses.calls) == 1

        report_items = processor.report.get_report()
        failed_report_items = [
            item for item in report_items if item.name() == "Failed Upload"
        ]
        assert len(failed_report_items) == 1


@responses.activate
def test_process_does_not_increment_tally_when_exception_occurs(
    processor_with_valid_credentials, test_photo, tally
):
    mock_failed_upload_response()

    with pytest.raises(RuntimeError):
        with patch("time.sleep"):
            processor_with_valid_credentials.process(test_photo)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") is None


## Retry behaviour tests


@responses.activate
def test_process_retries_upload_on_transient_failure(
    processor_with_valid_credentials, test_photo
):
    # First two calls fail, third succeeds
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        json={"error": {"message": "Upload failed"}},
        status=500,
    )
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        json={"error": {"message": "Upload failed"}},
        status=500,
    )
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        body="upload-token-12345",
        status=200,
        content_type="text/plain",
    )

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        with patch("time.sleep"):  # Avoid actually sleeping
            processor_with_valid_credentials.process(test_photo)

    assert len(responses.calls) == 3


@responses.activate
def test_process_succeeds_after_retry(
    processor_with_valid_credentials, test_photo, tally
):
    # First call fails, second succeeds
    responses.add(
        responses.POST,
        "https://photoslibrary.googleapis.com/v1/uploads",
        json={"error": {"message": "Upload failed"}},
        status=500,
    )
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        with patch("time.sleep"):  # Avoid actually sleeping
            processor_with_valid_credentials.process(test_photo)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 1


@responses.activate
def test_process_raises_after_max_retries_exhausted(
    processor_with_valid_credentials, test_photo, tally
):
    for _ in range(3):
        responses.add(
            responses.POST,
            "https://photoslibrary.googleapis.com/v1/uploads",
            json={"error": {"message": "Upload failed"}},
            status=500,
        )

    with pytest.raises(RuntimeError):
        with patch("time.sleep"):  # Avoid actually sleeping
            processor_with_valid_credentials.process(test_photo)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") is None


## Throttle behaviour tests


@responses.activate
def test_process_acquires_throttle_before_creating_media_item(
    processor_with_valid_credentials, test_photo
):
    mock_successful_upload_response()

    throttle = processor_with_valid_credentials._GooglePhotosUploadAfterEachProcessor__uploader._batch_create_throttle

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        with patch.object(throttle, "acquire", wraps=throttle.acquire) as mock_acquire:
            processor_with_valid_credentials.process(test_photo)

            assert mock_acquire.call_count == 1


## process method - database record tracking


@responses.activate
def test_process_records_uploaded_status_and_url_on_success(
    processor_with_valid_credentials, test_photo, repository
):
    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.process(test_photo)

    record = repository.find_by_path(test_photo.path)

    assert record is not None
    assert record["status"] == UploadStatus.UPLOADED.value
    assert record["uploaded_url"] == "https://photos.google.com/photo/AF1QipM_12345"
    assert record["file_path"] == str(test_photo.path)


@responses.activate
def test_process_records_failed_status_when_upload_exhausts_retries(
    processor_with_valid_credentials, test_photo, repository
):
    mock_failed_upload_responses(3)

    with pytest.raises(RuntimeError):
        with patch("time.sleep"):
            processor_with_valid_credentials.process(test_photo)

    record = repository.find_by_path(test_photo.path)

    assert record is not None
    assert record["status"] == UploadStatus.FAILED.value


## get_retryable


def test_get_retryable_yields_empty_list_when_no_retryable_rows(
    processor_with_valid_credentials,
):
    photos = list(processor_with_valid_credentials.get_retryable())

    assert photos == []


def test_get_retryable_yields_photo_for_each_retryable_row(
    processor_with_valid_credentials, repository, test_photo
):
    repository.upsert_pending(test_photo.path)

    photos = list(processor_with_valid_credentials.get_retryable())

    assert len(photos) == 1
    assert photos[0].path == test_photo.path


## resume


def test_resume_logs_when_no_retryable_photos(processor_with_valid_credentials, caplog):
    with caplog.at_level(logging.INFO):
        processor_with_valid_credentials.resume()

    info_logs = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.INFO and "No retryable" in r.getMessage(),
    )

    assert len(info_logs) == 1


def test_resume_processes_retryable_photo_in_dry_run(
    processor_dry_run, test_photo, caplog
):
    repo = GooglePhotosUploadRepository(processor_dry_run.context.database)
    repo.upsert_pending(test_photo.path)

    with caplog.at_level(logging.INFO):
        processor_dry_run.resume()

    uploaded_logs = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.INFO and r.getMessage().startswith("Uploaded"),
    )

    assert len(uploaded_logs) == 1


@responses.activate
def test_resume_uploads_retryable_photo(
    processor_with_valid_credentials, repository, test_photo, tally
):
    repository.upsert_pending(test_photo.path)

    mock_successful_upload_response()

    with mock_successful_media_item_creation(processor_with_valid_credentials):
        processor_with_valid_credentials.resume()

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 1
