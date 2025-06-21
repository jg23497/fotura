from pathlib import PosixPath
from .report_item import ReportItem


class FailedReportItem(ReportItem):
    def __init__(self, source: PosixPath, destination: PosixPath, exception: Exception):
        super().__init__()
        self.source = str(source)
        self.destination = str(destination)
        self.exception = str(exception)

    def name(self):
        return "Failed"

    def as_dict(self):
        return {
            "source": self.source,
            "destination": self.destination,
            "exception": self.exception,
        }
