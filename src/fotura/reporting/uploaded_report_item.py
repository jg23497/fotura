from pathlib import Path

from .report_item import ReportItem


class UploadedReportItem(ReportItem):
    def __init__(self, source: Path, destination: str):
        super().__init__()
        self.source = str(source)
        self.destination = destination

    def name(self):
        return "Uploaded"

    def as_dict(self):
        return {"source": self.source, "destination": self.destination}
