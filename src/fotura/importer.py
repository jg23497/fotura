import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from platformdirs import user_config_dir, user_data_dir

from fotura.importing.conflict_resolution import registry
from fotura.importing.media_finder import MediaFinder
from fotura.importing.synchronized_counter import SynchronizedCounter
from fotura.io.files import Files
from fotura.io.path_resolver import PathResolver
from fotura.processors.context import Context
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.reporting.logging_config import configure_report

logger = logging.getLogger(__name__)


class Importer:
    def __init__(
        self,
        input_path: Path,
        target_root: Path,
        dry_run: bool = False,
        enabled_before_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_all_processors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        open_report: bool = False,
        conflict_resolution_strategy: str = "keep_both",
        target_path_format: str = "%Y/%Y-%m",
    ):
        self.input_path = input_path
        self.target_root = target_root
        self.dry_run = dry_run
        self.target_path_format = target_path_format
        self.open_report = open_report
        self.tally = SynchronizedCounter({"errored": 0})

        self.__configure_dependencies(
            conflict_resolution_strategy,
            enabled_before_each_processors,
            enabled_after_each_processors,
            enabled_after_all_processors,
        )

    def process_photos(self):
        logger.info(
            "Importing photos from %s to %s (dry-run: %s)",
            self.input_path,
            self.target_root,
            str(self.dry_run).lower(),
        )

        self.files.has_read_write_permissions(self.input_path)

        processed_photos = []

        try:
            for photo in self.media_finder.find():
                try:
                    if self.__process_photo(photo):
                        processed_photos.append(photo)
                except Exception:
                    photo.log(logging.ERROR, "Failed to import", exc_info=True)
                    self.tally.increment("errored")
                    break

            if processed_photos:
                self.processor_orchestrator.run_after_all_processors(processed_photos)
        finally:
            self.__close_report()

    def __process_photo(self, photo) -> bool:
        self.files.ensure_writable(photo)
        self.processor_orchestrator.run_before_each_processors(photo)
        target_path = self.path_resolver.get_target_path(photo)

        if target_path is not None:
            self.files.move(photo, target_path)
            self.tally.increment("moved")
            self.processor_orchestrator.run_after_each_processors(photo)
            return True
        else:
            self.tally.increment("skipped")
            return False

    def __configure_dependencies(
        self,
        conflict_resolution_strategy,
        enabled_before_each_processors,
        enabled_after_each_processors,
        enabled_after_all_processors,
    ):
        self.user_config_path = Path(user_config_dir("fotura"))
        self.user_data_path = Path(user_data_dir("fotura"))

        self.__setup_report()

        self.conflict_resolver = registry.get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.media_finder = MediaFinder(self.input_path)
        self.files = Files(self.dry_run)
        self.path_resolver = PathResolver(
            self.target_root,
            self.target_path_format,
            self.conflict_resolver,
            self.dry_run,
        )

        processor_context = Context(
            user_config_path=self.user_config_path,
            dry_run=self.dry_run,
            tally=self.tally,
        )

        self.processor_orchestrator = ProcessorOrchestrator(
            processor_context,
            enabled_before_each_processors,
            enabled_after_each_processors,
            enabled_after_all_processors,
        )

    def __setup_report(self):
        report_dir = self.user_data_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_path = report_dir / f"import-report-{timestamp}.html"

        self.html_report_handler = configure_report(self.report_path)

    def __close_report(self):
        self.html_report_handler.close(self.tally)
        if self.open_report:
            webbrowser.open(self.report_path.as_uri())
