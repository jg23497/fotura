from sqlite3 import ProgrammingError

import pytest

from fotura.persistence.database import Database


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def database(database_path):
    with Database(database_path) as db:
        yield db


def test_constructor_creates_database_file_when_file_path_specified(database_path):
    with Database(database_path) as db:
        cursor = db.connection.execute("PRAGMA database_list")
        db_file = cursor.fetchone()[2]

        assert db_file == str(database_path)


def test_creates_parent_directories(tmp_path):
    database_path = tmp_path / "nested" / "dir" / "test.db"
    with Database(database_path):
        assert database_path.exists()


def test_uses_write_ahead_log_journal_mode(database):
    cursor = database.connection.execute("PRAGMA journal_mode")

    mode = cursor.fetchone()[0]

    assert mode == "wal"


def test_creates_tables_from_schema(database):
    cursor = database.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )

    tables = [row[0] for row in cursor.fetchall()]

    assert "google_photos_uploads" in tables


def test_schema_is_idempotent(database_path):
    with Database(database_path):
        pass

    with Database(database_path) as db:
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='google_photos_uploads'"
        )
        assert cursor.fetchone() is not None


def test_close_closes_connection(database):
    database.close()
    with pytest.raises(ProgrammingError):
        database.connection.execute("SELECT 1")


def test_constructor_without_file_path_returns_in_memory_database():
    with Database() as db:
        cursor = db.connection.execute("PRAGMA database_list")
        db_file = cursor.fetchone()[2]

        assert db_file == ""


def test_context_manager_closes_connection(database_path):
    with Database(database_path) as db:
        db.connection.execute("SELECT 1")

    with pytest.raises(ProgrammingError):
        db.connection.execute("SELECT 1")
