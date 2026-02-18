import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fotura.persistence.schema import ALL_TABLES

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, database_path: Optional[Path] = None) -> None:
        if database_path is not None:
            self.__configure_file_database(database_path)
        else:
            self.__configure_in_memory_database()

        self.__connection.row_factory = sqlite3.Row
        self.__connection.execute("PRAGMA journal_mode=WAL")
        self.__ensure_table_existence()

    @property
    def connection(self) -> sqlite3.Connection:
        return self.__connection

    def __configure_file_database(self, path: Path) -> None:
        logger.debug("Using SQLite database at: %s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.__connection = sqlite3.connect(str(path), check_same_thread=False)

    def __configure_in_memory_database(self) -> None:
        logger.debug("Using in-memory SQLite database")
        self.__connection = sqlite3.connect(":memory:", check_same_thread=False)

    def __ensure_table_existence(self) -> None:
        for table_sql in ALL_TABLES:
            self.__connection.execute(table_sql)
        self.__connection.commit()

    def close(self) -> None:
        self.__connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
