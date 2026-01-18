import logging
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console
from rich.logging import RichHandler

from fotura.importing.synchronized_counter import SynchronizedCounter


class PhotoPrefixFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        media_file = getattr(record, "media_file", None)
        if media_file:
            record.prefix = f"[{media_file}] "
        else:
            record.prefix = ""
        return True


class HTMLReportHandler(logging.Handler):
    def __init__(self, output_path: Path):
        super().__init__()
        self.output_path = output_path
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

        photo_entries = {k: v for k, v in self.entries.items() if k != "General"}
        return template.render(
            entries=general_entries,
            photo_entries=photo_entries,
            summary_attributes=summary_attributes.get_snapshot(),
        )

    def emit(self, record: logging.LogRecord) -> None:
        media_file = getattr(record, "media_file", None)
        key = str(media_file) if media_file else "General"

        entry = {
            "level": record.levelname.lower(),
            "levelname": record.levelname,
            "message": record.getMessage(),
            "exception": None,
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


def configure_report(report_path: Path):
    root_logger = logging.getLogger()

    html_handler = HTMLReportHandler(report_path)
    html_handler.setLevel(logging.INFO)

    root_logger.addHandler(html_handler)
    return html_handler
