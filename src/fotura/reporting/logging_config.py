import logging
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console
from rich.logging import RichHandler

from fotura.reporting.report_category import ReportCategory
from fotura.utils.synchronized_counter import SynchronizedCounter

OAUTH_FLOW_LOGGER = "google_auth_oauthlib.flow"


class PhotoPrefixFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        media_file = getattr(record, "media_file", None)
        if media_file:
            record.prefix = f"[{media_file}] "
        else:
            record.prefix = ""
        return True


class HTMLReportHandler(logging.Handler):
    def __init__(self, output_path: Path, dry_run: bool = False):
        super().__init__()
        self.output_path = output_path
        self.__dry_run = dry_run
        self.entries: dict[str, list[logging.LogRecord]] = {}
        self._template_env: Optional[Environment] = None
        self.template_name = "report_template.html"
        self.setFormatter(logging.Formatter())

    def __get_template_env(self) -> Environment:
        if self._template_env is None:
            template_dir = Path(__file__).parent / "templates"
            self._template_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        return self._template_env

    def __generate_html(self, summary_attributes: SynchronizedCounter) -> str:
        template_env = self.__get_template_env()
        template = template_env.get_template(self.template_name)

        general_entries = self.entries.get("General", [])
        file_entries = {k: v for k, v in self.entries.items() if k != "General"}
        skipped_entries = {
            key: records
            for key, records in file_entries.items()
            if any(
                record["report_category"] is ReportCategory.skipped
                for record in records
            )
        }
        ignored_entries = {
            key: records
            for key, records in file_entries.items()
            if any(
                record["report_category"] is ReportCategory.ignored
                for record in records
            )
        }
        media_entries = {
            key: records
            for key, records in file_entries.items()
            if key not in skipped_entries and key not in ignored_entries
        }
        summary = summary_attributes.get_snapshot()
        summary[ReportCategory.ignored.value] = len(ignored_entries)

        return template.render(
            entries=general_entries,
            skipped_entries=skipped_entries,
            ignored_entries=ignored_entries,
            media_entries=media_entries,
            summary_attributes=summary,
            dry_run=self.__dry_run,
        )

    def emit(self, record: logging.LogRecord) -> None:
        media_file = getattr(record, "media_file", None)
        key = str(media_file) if media_file else "General"

        entry = {
            "level": record.levelname.lower(),
            "levelname": record.levelname,
            "message": record.getMessage(),
            "exception": None,
            "report_category": getattr(record, "report_category", None),
        }

        if record.exc_info:
            entry["exception"] = self.formatter.formatException(record.exc_info)

        self.entries.setdefault(key, []).append(entry)

    def close(
        self, summary_attributes: SynchronizedCounter = SynchronizedCounter()
    ) -> None:
        # Ensure close is not called twice on shutdown
        root_logger = logging.getLogger()
        root_logger.removeHandler(self)

        html_content = self.__generate_html(summary_attributes)
        self.output_path.write_text(html_content, encoding="utf-8")
        super().close()


def setup_logging(
    level: int = logging.INFO,
    console: Optional[Console] = None,
    show_path: bool = True,
    rich_tracebacks: bool = True,
) -> None:
    logging.getLogger(OAUTH_FLOW_LOGGER).setLevel(logging.WARNING)

    if console is None:
        console = Console(stderr=True)

    handler = RichHandler(
        console=console,
        show_path=show_path,
        rich_tracebacks=rich_tracebacks,
        tracebacks_show_locals=False,
        markup=False,
        show_time=True,
        show_level=True,
        level=level,
        log_time_format="[%X]",
    )

    formatter = logging.Formatter("%(prefix)s%(message)s")
    handler.setFormatter(formatter)
    handler.addFilter(PhotoPrefixFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def configure_report(report_path: Path, dry_run: bool = False):
    root_logger = logging.getLogger()

    html_handler = HTMLReportHandler(report_path, dry_run=dry_run)
    html_handler.setLevel(logging.INFO)

    root_logger.addHandler(html_handler)
    return html_handler
