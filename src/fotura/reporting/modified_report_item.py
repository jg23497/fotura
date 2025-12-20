from pathlib import Path

from .report_item import ReportItem


class ModifiedReportItem(ReportItem):
    def __init__(self, source: Path, description: str):
        super().__init__()
        self.source = str(source)
        self.description = description

    def name(self):
        return "Modified"

    def as_dict(self):
        return {"source": self.source, "description": self.description}
