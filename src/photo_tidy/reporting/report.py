import logging
import sys
from datetime import datetime
from pathlib import Path
from .report_item import ReportItem

logger = logging.getLogger(__name__)


class Report:
    def __init__(self):
        self.report_items = []

    def log(self, item: ReportItem):
        self.report_items.append(item)

        frame = sys._getframe(1)

        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname=frame.f_code.co_filename,
            lineno=frame.f_lineno,
            msg=str(item),
            args=(),
            exc_info=None,
            func=frame.f_code.co_name,
        )
        logger.handle(record)

    def get_report(self) -> list[ReportItem]:
        return self.report_items

    def _generate_html(self) -> str:
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <title>PhotoTidy Report</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 20px; }",
            "        table { border-collapse: collapse; width: 100%; }",
            "        th, td { border: 1px solid #ddd; padding: 8px; }",
            "        th { background-color: #575757; color: white; }",
            "        .main-report-table > tbody > tr:nth-child(even) { background-color: #f2f2f2; }",
            "        .timestamp { color: #666; font-size: 0.9em; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <h1>PhotoTidy Report</h1>",
            f"    <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "    <table class='main-report-table'>",
            "        <tr><th>Timestamp</th><th>Event</th><th>Details</th></tr>",
            "        <tbody>",
        ]

        for item in self.report_items:
            details = item.as_dict()
            details_html = (
                "<table style='width:auto;border:none;'>"
                + "".join(
                    f"<tr><td style='border:none;padding:0 8px 0 0;'><b>{key}</b></td><td style='border:none;padding:0;'>{value}</td></tr>"
                    for key, value in details.items()
                )
                + "</table>"
            )
            html.append(
                f"<tr>"
                f"<td class='timestamp'>{item.timestamp}</td>"
                f"<td>{item.name()}</td>"
                f"<td>{details_html}</td>"
                f"</tr>"
            )

        html.extend(["        </tbody>", "    </table>", "</body>", "</html>"])

        return "\n".join(html)

    def create_report(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_report = self._generate_html()
        output_path.write_text(html_report, encoding="utf-8")
