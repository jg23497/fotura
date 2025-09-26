from pathlib import Path
from photo_tidy.reporting.report import Report


class Context:
    def __init__(self, report: Report, user_config_path: Path, dry_run: bool = False):
        super().__init__()
        self.report = report
        self.user_config_path = user_config_path
        self.dry_run = dry_run
