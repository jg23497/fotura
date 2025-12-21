import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fotura.reporting.failed_report_item import FailedReportItem
from fotura.reporting.initialize_report_item import InitializeReportItem
from fotura.reporting.move_report_item import MoveReportItem
from fotura.reporting.report_item import ReportItem
from fotura.reporting.skipped_report_item import SkippedReportItem

logger = logging.getLogger(__name__)


class Report:
    def __init__(self):
        self.report_items: List[ReportItem] = []
        self._template_env = None
        self.report_path = None

    def log(self, item: ReportItem):
        self.report_items.append(item)

        frame = sys._getframe(1)

        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname=frame.f_code.co_filename,
            lineno=frame.f_lineno,
            msg=item,
            args=(),
            exc_info=None,
            func=frame.f_code.co_name,
        )
        logger.handle(record)

    def get_report(self) -> List[ReportItem]:
        return self.report_items

    def create_report(self, output_path: Path, dry_run: bool = False) -> None:
        logger.info(f"Creating report at: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_report = self.__generate_html(dry_run)
        output_path.write_text(html_report, encoding="utf-8")
        self.report_path = output_path

    def open(self):
        if self.report_path is not None:
            logger.info("Opening report in browser")
            webbrowser.open(self.report_path.as_uri())

    def __get_summary_stats(self) -> dict:
        moved_count = sum(
            1 for item in self.report_items if type(item) is MoveReportItem
        )
        skipped_count = sum(
            1 for item in self.report_items if type(item) is SkippedReportItem
        )
        failed_count = sum(
            1 for item in self.report_items if type(item) is FailedReportItem
        )
        initialize_events = [
            item for item in self.report_items if type(item) is InitializeReportItem
        ]
        initialize_event = initialize_events[0] if initialize_events else None

        return {
            "moved_count": moved_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "initialize_event": initialize_event,
        }

    def __get_template_env(self):
        if self._template_env is None:
            template_dir = Path(__file__).parent.parent / "templates"
            self._template_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        return self._template_env

    def __generate_html(self, dry_run: bool = False) -> str:
        template_env = self.__get_template_env()
        template = template_env.get_template("report.html")

        summary_stats = self.__get_summary_stats()

        context = {
            "report_items": self.report_items,
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": dry_run,
            **summary_stats,
        }

        return template.render(context)
