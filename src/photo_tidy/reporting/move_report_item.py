from pathlib import Path

from .report_item import ReportItem


class MoveReportItem(ReportItem):
    def __init__(self, source: Path, destination: Path):
        super().__init__()
        self.source = str(source)
        self.destination = str(destination)

    def name(self):
        return "Moved"

    def as_dict(self):
        return {"source": self.source, "destination": self.destination}
