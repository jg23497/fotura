from photo_tidy.reporting.report import Report


class Context:
    def __init__(self, report: Report, dry_run: bool = False):
        super().__init__()
        self.report = report
        self.dry_run = dry_run
