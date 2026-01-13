from pathlib import Path


class Context:
    def __init__(self, user_config_path: Path, dry_run: bool = False):
        super().__init__()
        self.user_config_path = user_config_path
        self.dry_run = dry_run
