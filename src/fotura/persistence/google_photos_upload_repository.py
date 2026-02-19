import threading
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Row
from typing import List, Optional

from fotura.persistence.database import Database
from fotura.persistence.upload_status import UploadStatus

RETRYABLE_STATUSES = (
    UploadStatus.PENDING.value,
    UploadStatus.UPLOADING.value,
    UploadStatus.FAILED.value,
)


class GooglePhotosUploadRepository:
    def __init__(self, database: Database) -> None:
        self.__connection = database.connection
        self.__lock = threading.Lock()

    def upsert_pending(self, file_path: Path) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with self.__lock:
            self.__connection.execute(
                """
                INSERT INTO google_photos_uploads
                    (file_path, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    status = ?,
                    updated_at = excluded.updated_at
                """,
                (
                    str(file_path),
                    UploadStatus.PENDING.value,
                    now,
                    now,
                    UploadStatus.PENDING.value,
                ),
            )
            self.__connection.commit()

    def update_status(
        self,
        file_path: Path,
        status: UploadStatus,
        uploaded_url: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.__lock:
            self.__connection.execute(
                """
                UPDATE google_photos_uploads
                SET status = ?, uploaded_url = ?, updated_at = ?
                WHERE file_path = ?
                """,
                (status.value, uploaded_url, now, str(file_path)),
            )
            self.__connection.commit()

    def find_by_path(self, file_path: Path) -> Optional[Row]:
        with self.__lock:
            cursor = self.__connection.execute(
                "SELECT * FROM google_photos_uploads WHERE file_path = ?",
                (str(file_path),),
            )
            return cursor.fetchone()

    def find_retryable(self) -> List[Row]:
        with self.__lock:
            cursor = self.__connection.execute(
                "SELECT * FROM google_photos_uploads WHERE status IN (?, ?, ?)",
                RETRYABLE_STATUSES,
            )
            return cursor.fetchall()

    def count_retryable(self) -> int:
        with self.__lock:
            cursor = self.__connection.execute(
                "SELECT COUNT(*) FROM google_photos_uploads WHERE status IN (?, ?, ?)",
                RETRYABLE_STATUSES,
            )
            return cursor.fetchone()[0]
