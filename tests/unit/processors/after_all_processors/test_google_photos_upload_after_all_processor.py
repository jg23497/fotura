import contextlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import responses
from google.oauth2.credentials import Credentials

from fotura.domain.photo import Photo
from fotura.processors.after_all_processors.google_photos_upload_after_all_processor import (
    GooglePhotosUploadAfterAllProcessor,
)
from fotura.processors.context import Context
from fotura.processors.processor_setup_error import ProcessorSetupError
from fotura.utils.synchronized_counter import SynchronizedCounter
from tests.helpers.helper import get_log_entries


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


def get_client_service(processor):
    return processor._GooglePhotosUploadAfterAllProcessor__uploader._client.service


# Fixtures


@pytest.fixture
def tally():
    return SynchronizedCounter({"errored": 0})


@pytest.fixture(autouse=True)
def mock_photoslibrary_service():
    with patch("fotura.integrations.google_photos.client.build") as mock_build:
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
def processor(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
    return GooglePhotosUploadAfterAllProcessor(context)


@pytest.fixture
def processor_dry_run(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=True)
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
def test_photo_unsupported(fs):
    test_path = Path("test_file.txt")
    fs.create_file(test_path, contents=b"text file")
    return Photo(test_path)


# Tests


## initializer


def test_raises_value_error_if_concurrency_less_than_1(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
    with pytest.raises(ValueError, match=r"concurrency must be between 1 and 5"):
        GooglePhotosUploadAfterAllProcessor(context, concurrency=0)


def test_raises_value_error_if_concurrency_greater_than_max(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
    with pytest.raises(ValueError, match=r"concurrency must be between 1 and 5"):
        GooglePhotosUploadAfterAllProcessor(context, concurrency=10)


def test_raises_value_error_if_batch_size_less_than_1(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
    with pytest.raises(ValueError, match=r"batch_size must be between 1 and 50"):
        GooglePhotosUploadAfterAllProcessor(context, batch_size=0)


def test_raises_value_error_if_batch_size_greater_than_max(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
    with pytest.raises(ValueError, match=r"batch_size must be between 1 and 50"):
        GooglePhotosUploadAfterAllProcessor(context, batch_size=51)


def test_accepts_valid_boundary_values(secrets_dir, tally):
    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)

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

    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
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

    context = Context(user_config_path=secrets_dir, tally=tally, dry_run=False)
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
