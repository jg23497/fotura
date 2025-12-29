import logging
import os
import sys
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
from fotura.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
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
        self.__configure_processors(enabled_preprocessors, enabled_postprocessors)

    def process_photos(self):
        self.report.log(
            InitializeReportItem(self.dry_run, self.input_path, self.target_root)
        )

        claimed_paths = set[Path]()

        for photo in self.media_finder.find():
            target_path = Path()

            try:
                self.files.ensure_writable(photo)
                photo.facts = self.__run_preprocessors(photo)
                target_path = self.__get_target_path(photo, claimed_paths)
                if target_path is not None:
                    self.files.move(photo, target_path)
                    self.__run_postprocessors(photo, target_path)
            except Exception as e:
                self.report.log(FailedReportItem(photo.path, target_path, e))
                break

        self.__write_report()

    def __initialize_dependencies(self, conflict_resolution_strategy: str) -> None:
        self.preprocessors = []
        self.postprocessors = []
        self.report = Report()
        self.user_config_path = Path(user_config_dir("fotura"))
        self.user_data_path = Path(user_data_dir("fotura"))
        self.processor_context = Context(
            report=self.report,
            user_config_path=self.user_config_path,
            dry_run=self.dry_run,
        )
        self.conflict_resolver = self.__get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.media_finder = MediaFinder(self.input_path, self.report)
        self.files = Files(self.report, self.dry_run)
        self.__test_read_write_permissions()

    def __get_conflict_resolver(self, strategy: str):
        if strategy in STRATEGIES:
            return STRATEGIES[strategy]()
        else:
            raise ValueError(f"Unsupported conflict resolution strategy: {strategy}")

    def __test_read_write_permissions(self):
        temp_path = Path(self.input_path / "permission-check.tmp")

        if not temp_path.exists():
            try:
                with open(temp_path, "w") as f:
                    f.write("test")
            except Exception as e:
                raise PermissionError(
                    f"Permission check: Failed to write test file under {self.input_path}': {e}"
                ) from e

        try:
            os.remove(temp_path)
        except Exception as e:
            raise PermissionError(
                f"Permission check: Failed to remove test file under '{temp_path}': {e}"
            ) from e

        return True

    def __configure_processors(
        self,
        enabled_preprocessors: Optional[List[Tuple[str, Dict[str, Any]]]],
        enabled_postprocessors: Optional[List[Tuple[str, Dict[str, Any]]]],
    ) -> None:
        if enabled_preprocessors:
            self.__configure_processors_list(
                PREPROCESSOR_MAP, enabled_preprocessors, self.preprocessors
            )
        if enabled_postprocessors:
            self.__configure_processors_list(
                POSTPROCESSOR_MAP, enabled_postprocessors, self.postprocessors
            )

    def __configure_processors_list(
        self, processor_map, enabled_processors, processor_instances
    ) -> None:
        for processor_name, processor_args in enabled_processors:
            if processor_name in processor_map:
                instance = processor_map[processor_name](
                    context=self.processor_context, **processor_args
                )
                instance.configure()
                processor_instances.append(instance)
            else:
                logger.error(f"Unknown processor: {processor_name}")
                sys.exit(1)

    def __run_preprocessors(self, photo: Photo) -> Dict[FactType, Any]:
        facts: Dict[FactType, Any] = {}
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(photo.path):
                result = preprocessor.process(photo.path, facts)
                if result:
                    facts.update(result)
        return facts

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

    def __run_postprocessors(
        self,
        photo: Photo,
        target_path: Path,
    ):
        for postprocessor in self.postprocessors:
            if not postprocessor.can_handle(target_path):
                logger.warning(
                    f"{postprocessor.__class__.__name__}: Skipping {target_path}"
                )
                continue
            result = postprocessor.process(target_path, photo.facts)
            if result:
                photo.facts.update(result)

    def __write_report(self):
        report_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.user_data_path / "reports" / f"{report_name}.html"
        self.report.create_report(report_path, self.dry_run)

        if self.open_report:
            self.report.open()
