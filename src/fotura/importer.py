import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from platformdirs import user_config_dir, user_data_dir

from fotura.importing.conflict_resolution import registry
from fotura.importing.media_finder import MediaFinder
from fotura.io.files import Files
from fotura.io.path_resolver import PathResolver
from fotura.processors.context import Context
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.reporting import (
    FailedReportItem,
    InitializeReportItem,
    Report,
)

logger = logging.getLogger(__name__)


class Importer:
    def __init__(
        self,
        input_path: Path,
        target_root: Path,
        dry_run: bool = False,
        enabled_preprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        enabled_postprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        open_report: bool = False,
        conflict_resolution_strategy: str = "keep_both",
        target_path_format: str = "%Y/%Y-%m",
    ):
        self.input_path = input_path
        self.target_root = target_root
        self.dry_run = dry_run
        self.target_path_format = target_path_format
        self.open_report = open_report

        self.report = Report()
        self.user_config_path = Path(user_config_dir("fotura"))
        self.user_data_path = Path(user_data_dir("fotura"))
        self.conflict_resolver = registry.get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.media_finder = MediaFinder(self.input_path, self.report)
        self.files = Files(self.report, self.dry_run)
        self.path_resolver = PathResolver(
            self.target_root,
            self.target_path_format,
            self.conflict_resolver,
            self.report,
            self.dry_run,
        )

        processor_context = Context(
            report=self.report,
            user_config_path=self.user_config_path,
            dry_run=self.dry_run,
        )

        self.processor_orchestrator = ProcessorOrchestrator(
            processor_context, enabled_preprocessors, enabled_postprocessors
        )

    def process_photos(self):
        self.report.log(
            InitializeReportItem(self.dry_run, self.input_path, self.target_root)
        )

        self.files.test_read_write_permissions(self.input_path)

        for photo in self.media_finder.find():
            target_path = Path()
            try:
                self.__process_photo(photo)
            except Exception as e:
                self.report.log(FailedReportItem(photo.path, target_path, e))
                break

        self.report.write_report(self.user_data_path, self.dry_run, self.open_report)

    def __process_photo(self, photo):
        self.files.ensure_writable(photo)
        self.processor_orchestrator.run_preprocessors(photo)
        target_path = self.path_resolver.get_target_path(photo)

        if target_path is not None:
            self.files.move(photo, target_path)
            self.processor_orchestrator.run_postprocessors(photo, target_path)
