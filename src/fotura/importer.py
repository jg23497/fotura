import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from platformdirs import user_config_dir, user_data_dir

from fotura.conflict_resolution.registry import STRATEGIES
from fotura.domain.photo import Photo
from fotura.io.files import Files
from fotura.io.media_finder import MediaFinder
from fotura.io.photos.exif_data import ExifData
from fotura.path_format import PathFormat
from fotura.preprocessors.fact_type import FactType
from fotura.processors.context import Context
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.reporting import (
    FailedReportItem,
    InitializeReportItem,
    Report,
    SkippedReportItem,
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

        self.__initialize_dependencies(conflict_resolution_strategy)

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

        claimed_paths = set[Path]()

        for photo in self.media_finder.find():
            target_path = Path()

            try:
                self.files.ensure_writable(photo)
                photo.facts = self.processor_orchestrator.run_preprocessors(photo)
                target_path = self.__get_target_path(photo, claimed_paths)
                if target_path is not None:
                    self.files.move(photo, target_path)
                    self.processor_orchestrator.run_postprocessors(photo, target_path)
            except Exception as e:
                self.report.log(FailedReportItem(photo.path, target_path, e))
                break

        self.__write_report()

    def __initialize_dependencies(self, conflict_resolution_strategy: str) -> None:
        self.report = Report()
        self.user_config_path = Path(user_config_dir("fotura"))
        self.user_data_path = Path(user_data_dir("fotura"))
        self.conflict_resolver = self.__get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.media_finder = MediaFinder(self.input_path, self.report)
        self.files = Files(self.report, self.dry_run)
        self.files.test_read_write_permissions(self.input_path)

    def __get_conflict_resolver(self, strategy: str):
        if strategy in STRATEGIES:
            return STRATEGIES[strategy]()
        else:
            raise ValueError(f"Unsupported conflict resolution strategy: {strategy}")

    def __get_target_path(
        self, photo: Photo, claimed_paths: Set[Path]
    ) -> Optional[Path]:
        date = photo.facts.get(FactType.TAKEN_TIMESTAMP)

        if not date:
            date = ExifData.extract_date(photo.path)
        if not date:
            self.report.log(SkippedReportItem(photo.path, "No date found"))
            return None

        return self.__assign_target_path(date, photo.path, claimed_paths)

    def __assign_target_path(
        self, date: datetime, original_path: Path, claimed_paths: Set[Path]
    ) -> Optional[Path]:
        target_dir = PathFormat.build_path(
            self.target_root, date, self.target_path_format
        )

        if not self.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / f"{original_path.stem}{original_path.suffix}"

        if target_path in claimed_paths or target_path.exists():
            target_path = self.conflict_resolver.resolve(
                target_path=target_path,
                claimed_paths=claimed_paths,
            )
            if target_path is None:
                self.report.log(
                    SkippedReportItem(original_path, "Conflict resolution strategy")
                )
                return None

        claimed_paths.add(target_path)
        return target_path

    def __write_report(self):
        report_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.user_data_path / "reports" / f"{report_name}.html"
        self.report.create_report(report_path, self.dry_run)

        if self.open_report:
            self.report.open()
