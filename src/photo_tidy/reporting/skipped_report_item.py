from pathlib import PosixPath
from .report_item import ReportItem


class SkippedReportItem(ReportItem):
    def __init__(self, source: PosixPath, reason):
        super().__init__()
        self.source = str(source)
        self.reason = reason

    def name(self):
        return "Skipped"

    def as_dict(self):
        return {"source": self.source, "reason": self.reason}
