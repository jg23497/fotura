import pytest

from fotura.persistence.database import Database
from fotura.persistence.google_photos_upload_repository import (
    GooglePhotosUploadRepository,
)
from fotura.persistence.upload_status import UploadStatus


@pytest.fixture
def database(tmp_path):
    with Database(tmp_path / "test.db") as db:
        yield db


@pytest.fixture
def repository(database):
    return GooglePhotosUploadRepository(database)


class TestUpsertPending:
    def test_inserts_new_record(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")

        record = repository.find_by_hash("abc123")

        assert record is not None
        assert record["file_path"] == "/photos/image.jpg"
        assert record["status"] == "pending"
        assert record["uploaded_url"] is None
        assert record["created_at"] is not None
        assert record["updated_at"] is not None

    def test_updates_file_path_on_conflict(self, repository):
        repository.upsert_pending("/old/path.jpg", "abc123")
        repository.upsert_pending("/new/path.jpg", "abc123")

        record = repository.find_by_hash("abc123")

        assert record["file_path"] == "/new/path.jpg"
        assert record["status"] == "pending"

    def test_resets_status_to_pending_on_conflict(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")
        repository.update_status("abc123", UploadStatus.FAILED)
        repository.upsert_pending("/photos/image.jpg", "abc123")

        record = repository.find_by_hash("abc123")

        assert record["status"] == "pending"


class TestUpdateStatus:
    def test_updates_status(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")
        repository.update_status("abc123", UploadStatus.UPLOADED)

        record = repository.find_by_hash("abc123")

        assert record["status"] == "uploaded"

    def test_updates_status_with_url(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")
        repository.update_status(
            "abc123", UploadStatus.UPLOADED, "https://photos.google.com/photo/123"
        )

        record = repository.find_by_hash("abc123")

        assert record["status"] == "uploaded"
        assert record["uploaded_url"] == "https://photos.google.com/photo/123"

    def test_updates_updated_at_timestamp(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")
        record_before = repository.find_by_hash("abc123")

        repository.update_status("abc123", UploadStatus.FAILED)
        record_after = repository.find_by_hash("abc123")

        assert record_after["updated_at"] >= record_before["updated_at"]


class TestFindByHash:
    def test_returns_none_for_nonexistent_hash(self, repository):
        assert repository.find_by_hash("nonexistent") is None

    def test_returns_record_for_existing_hash(self, repository):
        repository.upsert_pending("/photos/image.jpg", "abc123")

        record = repository.find_by_hash("abc123")

        assert record is not None
        assert record["file_hash"] == "abc123"


class TestFindRetryable:
    def test_returns_empty_list_when_no_records(self, repository):
        assert repository.find_retryable() == []

    def test_returns_pending_records(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["file_hash"] == "hash_a"

    def test_returns_failed_records(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")
        repository.update_status("hash_a", UploadStatus.FAILED)

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["status"] == "failed"

    def test_returns_uploading_records(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")
        repository.update_status("hash_a", UploadStatus.UPLOADING)

        retryable = repository.find_retryable()

        assert len(retryable) == 1
        assert retryable[0]["status"] == "uploading"

    def test_returns_both_pending_and_failed(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")
        repository.upsert_pending("/photos/b.jpg", "hash_b")
        repository.update_status("hash_b", UploadStatus.FAILED)

        retryable = repository.find_retryable()

        assert len(retryable) == 2

    def test_excludes_uploaded_records(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")
        repository.update_status("hash_a", UploadStatus.UPLOADED)

        assert repository.find_retryable() == []


class TestCountRetryable:
    def test_returns_zero_when_no_records(self, repository):
        assert repository.count_retryable() == 0

    def test_counts_pending_failed_and_uploading(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")

        repository.upsert_pending("/photos/b.jpg", "hash_b")
        repository.update_status("hash_b", UploadStatus.FAILED)

        repository.upsert_pending("/photos/c.jpg", "hash_c")
        repository.update_status("hash_c", UploadStatus.UPLOADING)

        repository.upsert_pending("/photos/d.jpg", "hash_d")
        repository.update_status("hash_d", UploadStatus.UPLOADED)

        # All but d.jpg/hash_d
        assert repository.count_retryable() == 3

    def test_excludes_uploaded(self, repository):
        repository.upsert_pending("/photos/a.jpg", "hash_a")
        repository.update_status("hash_a", UploadStatus.UPLOADED)

        assert repository.count_retryable() == 0
