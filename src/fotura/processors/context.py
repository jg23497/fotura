from pathlib import Path
from typing import Optional

from fotura.persistence.database import Database
from fotura.utils.synchronized_counter import SynchronizedCounter


class Context:
    def __init__(
        self,
        user_config_path: Path,
        tally: SynchronizedCounter,
        dry_run: bool = False,
        database: Optional[Database] = None,
    ):
        super().__init__()

        self.user_config_path = user_config_path
        self.tally = tally
        self.dry_run = dry_run

        self.database = (
            database
            if database is not None
            else Database(user_config_path / "fotura.db")
        )
