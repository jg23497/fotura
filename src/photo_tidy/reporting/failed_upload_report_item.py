from pathlib import Path

from .report_item import ReportItem


class FailedUploadReportItem(ReportItem):
    def __init__(self, source: Path, exception: Exception):
        super().__init__()
        self.source = str(source)
        self.exception = str(exception)

    def name(self):
        return "Failed Upload"

    def as_dict(self):
        return {
            "source": self.source,
            "exception": self.exception,
        }
