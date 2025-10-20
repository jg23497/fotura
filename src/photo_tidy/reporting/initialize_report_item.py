from pathlib import Path

from .report_item import ReportItem


class InitializeReportItem(ReportItem):
    def __init__(self, dry_run: bool, input_path: Path, target_path: Path):
        super().__init__()
        self.dry_run = dry_run
        self.input_path = str(input_path)
        self.target_path = str(target_path)

    def name(self):
        return "Initialize"

    def as_dict(self):
        return {
            "dry_run": str(self.dry_run).lower(),
            "input_path": self.input_path,
            "target_path": self.target_path,
        }
