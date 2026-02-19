import contextlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import responses

from fotura.domain.photo import Photo
from fotura.persistence.database import Database
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.persistence.upload_status import UploadStatus
from fotura.processors.after_all_processors.google_photos_upload_after_all_processor import (
    GooglePhotosUploadAfterAllProcessor,
)
from fotura.processors.context import Context
from fotura.processors.processor_setup_error import ProcessorSetupError
from fotura.utils.file_hasher import hash_file
from tests.helpers.google_photos import (
    create_credentials,
    mock_failed_upload_responses,
    mock_installed_app_flow,
    mock_successful_upload_response,
    read_token,
    write_secret,
    write_token,
)
from tests.helpers.helper import get_log_entries


@contextlib.contextmanager
def mock_successful_batch_create(processor, num_items=1):
    with patch.object(get_client_service(processor), "mediaItems") as mock_media_items:
        mock_batch_create = Mock()
        mock_batch_create.return_value.execute.return_value = {
            "newMediaItemResults": [
                {
                    "mediaItem": {
                        "productUrl": f"https://photos.google.com/photo/AF1QipM_{i}"
                    }
                }
                for i in range(num_items)
            ]
        }
        mock_media_items.return_value.batchCreate = mock_batch_create
        yield mock_batch_create


def get_client_service(processor):
    return processor._GooglePhotosUploadAfterAllProcessor__uploader._client.service


# Fixtures


@pytest.fixture
def processor(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    return GooglePhotosUploadAfterAllProcessor(context)


@pytest.fixture
def processor_dry_run(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=True, database=Database()
    )
    return GooglePhotosUploadAfterAllProcessor(context)


@pytest.fixture
def processor_with_valid_credentials(secrets_dir, cached_credentials_valid, processor):
    write_token(secrets_dir, cached_credentials_valid)
    processor.configure()
    return processor


@pytest.fixture
def test_photos(fs):
    photos = []
    for i in range(3):
        path = Path(f"test_image_{i}.jpg")
        fs.create_file(path, contents=b"data")
        photos.append(Photo(path))
    return photos


@pytest.fixture
def test_photo(fs):
    test_image_path = Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"data")
    return Photo(test_image_path)


@pytest.fixture
def test_photo_png(fs):
    test_image_path = Path("test_image.png")
    fs.create_file(test_image_path, contents=b"data")
    return Photo(test_image_path)


@pytest.fixture
def unique_photos(fs):
    photos = []

    for i in range(3):
        path = Path(f"unique_{i}.jpg")
        fs.create_file(path, contents=f"unique_content_{i}".encode())
        photos.append(Photo(path))

    return photos


@pytest.fixture
def repository(processor_with_valid_credentials):
    return GooglePhotosUploadRepository(
        processor_with_valid_credentials.context.database
    )


@pytest.fixture
def test_photo_unsupported(fs):
    test_path = Path("test_file.txt")
    fs.create_file(test_path, contents=b"text file")
    return Photo(test_path)


# Tests


## initializer


def test_raises_value_error_if_concurrency_less_than_1(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    with pytest.raises(ValueError, match=r"concurrency must be between 1 and 5"):
        GooglePhotosUploadAfterAllProcessor(context, concurrency=0)


def test_raises_value_error_if_concurrency_greater_than_max(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    with pytest.raises(ValueError, match=r"concurrency must be between 1 and 5"):
        GooglePhotosUploadAfterAllProcessor(context, concurrency=10)


def test_raises_value_error_if_batch_size_less_than_1(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    with pytest.raises(ValueError, match=r"batch_size must be between 1 and 50"):
        GooglePhotosUploadAfterAllProcessor(context, batch_size=0)


def test_raises_value_error_if_batch_size_greater_than_max(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    with pytest.raises(ValueError, match=r"batch_size must be between 1 and 50"):
        GooglePhotosUploadAfterAllProcessor(context, batch_size=51)


def test_accepts_valid_boundary_values(secrets_dir, tally):
    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )

    processor_1 = GooglePhotosUploadAfterAllProcessor(
        context, concurrency=1, batch_size=1
    )
    assert processor_1.concurrency == 1
    assert processor_1.batch_size == 1

    processor_2 = GooglePhotosUploadAfterAllProcessor(
        context, concurrency=5, batch_size=50
    )
    assert processor_2.concurrency == 5
    assert processor_2.batch_size == 50


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

        assert get_client_service(processor) is not None
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

    flow = Mock()
    flow.run_local_server.return_value = create_credentials(
        expiry=(datetime.now() + timedelta(days=1)),
        refresh_token="refresh-token",
    )

    with mock_installed_app_flow(flow):
        processor.configure()

        credentials = read_token()
        assert "ya29.valid-token" in credentials.token
        assert get_client_service(processor) is not None


## process method


def test_process_raises_error_when_service_not_initialized(processor, test_photo):
    with pytest.raises(ProcessorSetupError):
        processor.process([test_photo])


@responses.activate
def test_process_skips_files_over_the_size_limit(
    processor_with_valid_credentials, caplog, fs
):
    oversized_path = Path("oversized.jpg")
    fs.create_file(oversized_path, st_size=200 * 1024 * 1024 + 1)
    oversized_photo = Photo(oversized_path)

    with caplog.at_level(logging.DEBUG):
        processor_with_valid_credentials.process([oversized_photo])

    assert len(responses.calls) == 0

    debug_logs = get_log_entries(
        caplog,
        lambda r: (
            r.levelno == logging.DEBUG and "Skipping unsupported" in r.getMessage()
        ),
    )
    assert len(debug_logs) == 1


@responses.activate
def test_process_skips_unsupported_file_extensions(
    processor_with_valid_credentials, test_photo, test_photo_unsupported, caplog
):
    photos = [test_photo, test_photo_unsupported]

    mock_successful_upload_response(1)

    with mock_successful_batch_create(processor_with_valid_credentials, 1):
        with caplog.at_level(logging.DEBUG):
            processor_with_valid_credentials.process(photos)

    debug_logs = get_log_entries(
        caplog,
        lambda r: (
            r.levelno == logging.DEBUG and "Skipping unsupported" in r.getMessage()
        ),
    )
    assert len(debug_logs) == 1


@responses.activate
def test_process_uploads_supported_photos_in_batch(
    processor_with_valid_credentials, test_photos, tally
):
    mock_successful_upload_response(3)

    with mock_successful_batch_create(
        processor_with_valid_credentials, 3
    ) as mock_batch_create:
        processor_with_valid_credentials.process(test_photos)

    assert mock_batch_create.call_count == 1
    called_body = mock_batch_create.call_args.kwargs["body"]
    assert len(called_body["newMediaItems"]) == 3


@responses.activate
def test_process_increments_tally_for_each_successful_upload(
    processor_with_valid_credentials, test_photos, tally
):
    mock_successful_upload_response(3)

    with mock_successful_batch_create(processor_with_valid_credentials, 3):
        processor_with_valid_credentials.process(test_photos)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 3


## process method - dry run


@responses.activate
def test_process_skips_upload_when_dry_run_enabled(processor_dry_run, test_photos):
    processor_dry_run.process(test_photos)

    assert len(responses.calls) == 0


def test_process_logs_dry_run_uploaded_message_when_dry_run_enabled(
    processor_dry_run, test_photos, caplog
):
    with caplog.at_level(logging.INFO):
        processor_dry_run.process(test_photos)

    log_entries = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.INFO and r.getMessage().startswith("Uploaded"),
    )

    assert len(log_entries) == 3


def test_process_increments_tally_when_dry_run_enabled(
    processor_dry_run, test_photos, tally
):
    processor_dry_run.process(test_photos)

    final_snapshot = tally.get_snapshot()
    assert final_snapshot.get("uploaded to google photos") == 3


## process method - batching behavior


@responses.activate
def test_process_splits_photos_into_batches(secrets_dir, tally, fs):
    photos = []
    for i in range(25):
        path = Path(f"test_{i}.jpg")
        fs.create_file(path, contents=b"data")
        photos.append(Photo(path))

    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    processor = GooglePhotosUploadAfterAllProcessor(context, batch_size=10)

    cached_credentials = create_credentials(expiry=datetime.now() + timedelta(days=1))
    write_token(secrets_dir, cached_credentials)
    processor.configure()

    mock_successful_upload_response(25)

    with mock_successful_batch_create(processor, 10) as mock_batch_create:
        mock_batch_create.return_value.execute.side_effect = [
            {
                "newMediaItemResults": [
                    {"mediaItem": {"productUrl": f"https://photos.google.com/{i}"}}
                    for i in range(10)
                ]
            },
            {
                "newMediaItemResults": [
                    {"mediaItem": {"productUrl": f"https://photos.google.com/{i}"}}
                    for i in range(10)
                ]
            },
            {
                "newMediaItemResults": [
                    {"mediaItem": {"productUrl": f"https://photos.google.com/{i}"}}
                    for i in range(5)
                ]
            },
        ]
        processor.process(photos)

    assert mock_batch_create.call_count == 3


## process method - retry and error handling


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
        body="upload-token-success",
        status=200,
        content_type="text/plain",
    )

    with mock_successful_batch_create(processor_with_valid_credentials, 1):
        with patch("time.sleep"):
            processor_with_valid_credentials.process([test_photo])

    assert len(responses.calls) == 3


@responses.activate
def test_process_continues_with_remaining_photos_after_upload_failure(
    secrets_dir, tally, fs
):
    photos = []
    for i in range(3):
        path = Path(f"test_{i}.jpg")
        fs.create_file(path, contents=b"data")
        photos.append(Photo(path))

    context = Context(
        user_config_path=secrets_dir, tally=tally, dry_run=False, database=Database()
    )
    processor = GooglePhotosUploadAfterAllProcessor(context, concurrency=1)

    cached_credentials = create_credentials(expiry=datetime.now() + timedelta(days=1))
    write_token(secrets_dir, cached_credentials)
    processor.configure()

    # First photo fails all retries, second and third succeed
    for _ in range(3):  # 3 retries for first photo
        responses.add(
            responses.POST,
            "https://photoslibrary.googleapis.com/v1/uploads",
            json={"error": {"message": "Upload failed"}},
            status=500,
        )

    # Second and third succeed
    mock_successful_upload_response(2)

    with mock_successful_batch_create(processor, 2):
        with patch("time.sleep"):
            processor.process(photos)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 2
    assert tally_snapshot.get("errored") == 1


@responses.activate
def test_process_retries_failed_batch_items_individually(
    processor_with_valid_credentials, test_photos, tally
):
    # Initial uploads for batch (3 photos)
    mock_successful_upload_response(3)

    # Retry upload for failed photo
    mock_successful_upload_response(1)

    with patch.object(
        get_client_service(processor_with_valid_credentials), "mediaItems"
    ) as mock_media_items:
        mock_batch_create = Mock()
        # First call: batch with partial failure, second call: retry succeeds
        mock_batch_create.return_value.execute.side_effect = [
            {
                "newMediaItemResults": [
                    {
                        "mediaItem": {
                            "productUrl": "https://photos.google.com/photo/success1"
                        }
                    },
                    {"status": {"message": "INVALID_ARGUMENT: Invalid upload token"}},
                    {
                        "mediaItem": {
                            "productUrl": "https://photos.google.com/photo/success2"
                        }
                    },
                ]
            },
            {
                "newMediaItemResults": [
                    {
                        "mediaItem": {
                            "productUrl": "https://photos.google.com/photo/retry_success"
                        }
                    }
                ]
            },
        ]
        mock_media_items.return_value.batchCreate = mock_batch_create

        processor_with_valid_credentials.process(test_photos)

    # All 3 should succeed (2 from batch + 1 from retry)
    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 3
    assert tally_snapshot.get("errored") == 0

    # batchCreate called twice: once for batch, once for retry
    assert mock_batch_create.call_count == 2


@responses.activate
def test_process_handles_retry_failure(
    processor_with_valid_credentials, test_photos, tally
):
    # Initial uploads for batch (3 photos)
    mock_successful_upload_response(3)

    # Retry upload for failed photo
    mock_successful_upload_response(1)

    with patch.object(
        get_client_service(processor_with_valid_credentials), "mediaItems"
    ) as mock_media_items:
        mock_batch_create = Mock()
        # First call: batch with partial failure, second call: retry also fails
        mock_batch_create.return_value.execute.side_effect = [
            {
                "newMediaItemResults": [
                    {
                        "mediaItem": {
                            "productUrl": "https://photos.google.com/photo/success1"
                        }
                    },
                    {"status": {"message": "INVALID_ARGUMENT: Invalid upload token"}},
                    {
                        "mediaItem": {
                            "productUrl": "https://photos.google.com/photo/success2"
                        }
                    },
                ]
            },
            {
                "newMediaItemResults": [
                    {"status": {"message": "INVALID_ARGUMENT: Still failing"}}
                ]
            },
        ]
        mock_media_items.return_value.batchCreate = mock_batch_create

        processor_with_valid_credentials.process(test_photos)

    tally_snapshot = tally.get_snapshot()
    assert tally_snapshot.get("uploaded to google photos") == 2
    assert tally_snapshot.get("errored") == 1


## throttle integration


@responses.activate
def test_batch_create_acquires_throttle_before_execution(
    processor_with_valid_credentials, test_photo
):
    mock_successful_upload_response(1)

    with mock_successful_batch_create(processor_with_valid_credentials, 1):
        # Access name-mangled attribute
        throttle = processor_with_valid_credentials._GooglePhotosUploadAfterAllProcessor__uploader._batch_create_throttle
        with patch.object(throttle, "acquire") as mock_acquire:
            processor_with_valid_credentials.process([test_photo])

    mock_acquire.assert_called_once()


## process - database record tracking


@responses.activate
def test_process_records_uploaded_status_and_url_on_success(
    processor_with_valid_credentials, test_photo, repository
):
    mock_successful_upload_response(1)

    with mock_successful_batch_create(processor_with_valid_credentials, 1):
        processor_with_valid_credentials.process([test_photo])

    record = repository.find_by_hash(hash_file(test_photo.path))

    assert record is not None
    assert record["status"] == UploadStatus.UPLOADED.value
    assert record["uploaded_url"] == "https://photos.google.com/photo/AF1QipM_0"
    assert record["file_path"] == str(test_photo.path)


@responses.activate
def test_process_records_failed_status_when_byte_upload_exhausts_retries(
    processor_with_valid_credentials, test_photo, repository
):
    mock_failed_upload_responses(3)

    with patch("time.sleep"):
        processor_with_valid_credentials.process([test_photo])

    record = repository.find_by_hash(hash_file(test_photo.path))

    assert record is not None
    assert record["status"] == UploadStatus.FAILED.value


@responses.activate
def test_process_records_failed_status_when_media_item_creation_fails_including_retry(
    processor_with_valid_credentials, test_photo, repository
):
    mock_successful_upload_response(2)  # one for each create media items call

    with patch.object(
        get_client_service(processor_with_valid_credentials), "mediaItems"
    ) as mock_media_items:
        mock_batch_create = Mock()
        mock_batch_create.return_value.execute.side_effect = [
            {"newMediaItemResults": [{"status": {"message": "INVALID_ARGUMENT"}}]},
            {"newMediaItemResults": [{"status": {"message": "INVALID_ARGUMENT"}}]},
        ]
        mock_media_items.return_value.batchCreate = mock_batch_create

        processor_with_valid_credentials.process([test_photo])

    record = repository.find_by_hash(hash_file(test_photo.path))

    assert record is not None
    assert record["status"] == UploadStatus.FAILED.value


@responses.activate
def test_process_records_separate_statuses_for_each_photo(
    processor_with_valid_credentials, unique_photos, repository
):
    mock_failed_upload_responses(3)  # first photo fails all retries
    mock_successful_upload_response(2)  # second and third succeed

    processor = GooglePhotosUploadAfterAllProcessor(
        processor_with_valid_credentials.context, concurrency=1
    )
    processor.configure()

    with mock_successful_batch_create(processor, 2):
        with patch("time.sleep"):
            processor.process(unique_photos)

    statuses = [
        repository.find_by_hash(hash_file(p.path))["status"] for p in unique_photos
    ]
    assert statuses.count(UploadStatus.FAILED.value) == 1
    assert statuses.count(UploadStatus.UPLOADED.value) == 2
