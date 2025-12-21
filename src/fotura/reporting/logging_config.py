import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


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
        markup=True,
        show_time=True,
        show_level=True,
        level=level,
        log_time_format="[%X]",  # (HH:MM:SS)
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    root_logger.addHandler(handler)
