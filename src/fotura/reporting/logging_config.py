import logging
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console
from rich.logging import RichHandler

from fotura.domain.photo_cluster import PhotoCluster
from fotura.reporting.photo_cluster_report import PhotoClusterReport
from fotura.reporting.report_category import ReportCategory
from fotura.utils.synchronized_counter import SynchronizedCounter

OAUTH_FLOW_LOGGER = "google_auth_oauthlib.flow"
ReportEntry = dict[str, Any]
FileEntries = dict[str, list[ReportEntry]]


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
        self.entries: FileEntries = {}
        self.__photo_cluster_report: Optional[PhotoClusterReport] = None
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

        clustered_entries, skipped_entries, ignored_entries, media_entries = (
            self.__build_file_sections()
        )

        summary = self.__build_summary(summary_attributes, len(ignored_entries))

        return template.render(
            entries=general_entries,
            skipped_entries=skipped_entries,
            ignored_entries=ignored_entries,
            media_entries=media_entries,
            clustered_entries=clustered_entries,
            clustering_enabled=self.__photo_cluster_report is not None,
            summary_attributes=summary,
            dry_run=self.__dry_run,
        )

    def __build_file_sections(
        self,
    ) -> tuple[list[dict[str, Any]], FileEntries, FileEntries, FileEntries]:
        file_entries = {
            key: records for key, records in self.entries.items() if key != "General"
        }
        skipped_entries = self.__entries_for_category(
            file_entries, ReportCategory.skipped
        )
        ignored_entries = self.__entries_for_category(
            file_entries, ReportCategory.ignored
        )

        clustered_entries, clustered_paths = self.__build_cluster_entries(file_entries)

        for path in clustered_paths:
            skipped_entries.pop(path, None)
            ignored_entries.pop(path, None)

        excluded_paths = (
            skipped_entries.keys() | ignored_entries.keys() | clustered_paths
        )
        media_entries = {
            key: records
            for key, records in file_entries.items()
            if key not in excluded_paths
        }

        return clustered_entries, skipped_entries, ignored_entries, media_entries

    @staticmethod
    def __entries_for_category(
        file_entries: FileEntries, category: ReportCategory
    ) -> FileEntries:
        return {
            key: records
            for key, records in file_entries.items()
            if any(record["report_category"] is category for record in records)
        }

    def __build_cluster_entries(
        self, file_entries: FileEntries
    ) -> tuple[list[dict[str, Any]], set[str]]:
        clustered_entries = []
        clustered_paths = set()
        if self.__photo_cluster_report is not None:
            clustered_entries, clustered_paths = (
                self.__photo_cluster_report.build_entries(file_entries)
            )

        return clustered_entries, clustered_paths

    @staticmethod
    def __build_summary(
        summary_attributes: SynchronizedCounter, ignored_count: int
    ) -> dict[str, int]:
        summary_snapshot = summary_attributes.get_snapshot()
        summary = {
            "errored": summary_snapshot.get("errored", 0),
            ReportCategory.ignored.value: ignored_count,
            ReportCategory.skipped.value: summary_snapshot.get(
                ReportCategory.skipped.value, 0
            ),
            "moved": summary_snapshot.get("moved", 0),
        }

        core_summary_keys = set(summary)
        summary.update(
            (key, value)
            for key, value in summary_snapshot.items()
            if key not in core_summary_keys
        )

        return summary

    def set_photo_clusters(self, photo_clusters: list[PhotoCluster]) -> None:
        self.__photo_cluster_report = PhotoClusterReport(photo_clusters)

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
