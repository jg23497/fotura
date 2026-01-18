from pathlib import Path

from fotura.importing.synchronized_counter import SynchronizedCounter


class Context:
    def __init__(
        self, user_config_path: Path, tally: SynchronizedCounter, dry_run: bool = False
    ):
        super().__init__()
        self.user_config_path = user_config_path
        self.tally = tally
        self.dry_run = dry_run
