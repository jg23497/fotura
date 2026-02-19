from pathlib import Path

import pytest

from fotura.persistence.database import Database
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.persistence.upload_status import UploadStatus

IMAGE = Path("/photos/image.jpg")
IMAGE_A = Path("/photos/a.jpg")
IMAGE_B = Path("/photos/b.jpg")
IMAGE_C = Path("/photos/c.jpg")
IMAGE_D = Path("/photos/d.jpg")


@pytest.fixture
def database(tmp_path):
    with Database(tmp_path / "test.db") as db:
        yield db


@pytest.fixture
def repository(database):
    return GooglePhotosUploadRepository(database)


class TestUpsertPending:
    def test_inserts_new_record(self, repository):
        repository.upsert_pending(IMAGE)

        record = repository.find_by_path(IMAGE)

        assert record is not None
        assert record["file_path"] == str(IMAGE)
        assert record["status"] == "pending"
        assert record["uploaded_url"] is None
        assert record["created_at"] is not None
        assert record["updated_at"] is not None

    def test_resets_status_to_pending_on_conflict(self, repository):
        repository.upsert_pending(IMAGE)
        repository.update_status(IMAGE, UploadStatus.FAILED)
        repository.upsert_pending(IMAGE)

        record = repository.find_by_path(IMAGE)

        assert record["status"] == "pending"


class TestUpdateStatus:
    def test_updates_status(self, repository):
        repository.upsert_pending(IMAGE)
        repository.update_status(IMAGE, UploadStatus.UPLOADED)

        record = repository.find_by_path(IMAGE)

        assert record["status"] == "uploaded"

    def test_updates_status_with_url(self, repository):
        repository.upsert_pending(IMAGE)
        repository.update_status(
            IMAGE, UploadStatus.UPLOADED, "https://photos.google.com/photo/123"
        )

        record = repository.find_by_path(IMAGE)

        assert record["status"] == "uploaded"
        assert record["uploaded_url"] == "https://photos.google.com/photo/123"

    def test_updates_updated_at_timestamp(self, repository):
        repository.upsert_pending(IMAGE)
        record_before = repository.find_by_path(IMAGE)

        repository.update_status(IMAGE, UploadStatus.FAILED)
        record_after = repository.find_by_path(IMAGE)

        assert record_after["updated_at"] >= record_before["updated_at"]


class TestFindByPath:
    def test_returns_none_for_nonexistent_path(self, repository):
        assert repository.find_by_path(Path("/nonexistent/image.jpg")) is None

    def test_returns_record_for_existing_path(self, repository):
        repository.upsert_pending(IMAGE)

        record = repository.find_by_path(IMAGE)

        assert record is not None
        assert record["file_path"] == str(IMAGE)


class TestFindRetryable:
    def test_returns_empty_list_when_no_records(self, repository):
        assert repository.find_retryable() == []

    def test_returns_pending_records(self, repository):
        repository.upsert_pending(IMAGE_A)

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["file_path"] == str(IMAGE_A)

    def test_returns_failed_records(self, repository):
        repository.upsert_pending(IMAGE_A)
        repository.update_status(IMAGE_A, UploadStatus.FAILED)

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["status"] == "failed"

    def test_returns_uploading_records(self, repository):
        repository.upsert_pending(IMAGE_A)
        repository.update_status(IMAGE_A, UploadStatus.UPLOADING)

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["status"] == "uploading"

    def test_returns_both_pending_and_failed(self, repository):
        repository.upsert_pending(IMAGE_A)
        repository.upsert_pending(IMAGE_B)
        repository.update_status(IMAGE_B, UploadStatus.FAILED)

        retryable = repository.find_retryable()

        assert len(retryable) == 2

    def test_excludes_uploaded_records(self, repository):
        repository.upsert_pending(IMAGE_A)
        repository.update_status(IMAGE_A, UploadStatus.UPLOADED)

        assert repository.find_retryable() == []


class TestCountRetryable:
    def test_returns_zero_when_no_records(self, repository):
        assert repository.count_retryable() == 0

    def test_counts_pending_failed_and_uploading(self, repository):
        repository.upsert_pending(IMAGE_A)

        repository.upsert_pending(IMAGE_B)
        repository.update_status(IMAGE_B, UploadStatus.FAILED)

        repository.upsert_pending(IMAGE_C)
        repository.update_status(IMAGE_C, UploadStatus.UPLOADING)

        repository.upsert_pending(IMAGE_D)
        repository.update_status(IMAGE_D, UploadStatus.UPLOADED)

        # All but IMAGE_D
        assert repository.count_retryable() == 3

    def test_excludes_uploaded(self, repository):
        repository.upsert_pending(IMAGE_A)
        repository.update_status(IMAGE_A, UploadStatus.UPLOADED)

        assert repository.count_retryable() == 0
