import logging
import os
import shutil
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from platformdirs import user_config_dir, user_data_dir

from photo_tidy.conflict_resolution.registry import STRATEGIES
from photo_tidy.exif_data import ExifData
from photo_tidy.path_format import PathFormat
from photo_tidy.preprocessors.fact_type import FactType
from photo_tidy.processors.context import Context
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.reporting import (
    FailedReportItem,
    InitializeReportItem,
    MoveReportItem,
    Report,
    SkippedReportItem,
)
from photo_tidy.services.photo_finder import PhotoFinder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Tidy:
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

        for file_path in self.photo_finder.find_photos():
            target_path = Path()

            try:
                self.__remove_read_only_flag(file_path)
                facts = self.__run_preprocessors(file_path)
                target_path = self.__get_target_path(file_path, facts, claimed_paths)
                if target_path is not None:
                    self.__move_photo(file_path, target_path)
                    self.__run_postprocessors(target_path, facts)
            except Exception as e:
                self.report.log(FailedReportItem(file_path, target_path, e))
                break

        self.__write_report()

    def __initialize_dependencies(self, conflict_resolution_strategy: str) -> None:
        self.preprocessors = []
        self.postprocessors = []
        self.report = Report()
        self.user_config_path = Path(user_config_dir("phototidy"))
        self.user_data_path = Path(user_data_dir("phototidy"))
        self.processor_context = Context(
            report=self.report,
            user_config_path=self.user_config_path,
            dry_run=self.dry_run,
        )
        self.conflict_resolver = self.__get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.photo_finder = PhotoFinder(self.input_path, self.report)
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

    def __remove_read_only_flag(self, file_path):
        if self.dry_run:
            return
        try:
            # Windows: ensure FILE_ATTRIBUTE_READONLY is removed.
            # Unix: ensure user-write bit is set.
            current_mode = file_path.stat().st_mode
            new_mode = current_mode | stat.S_IWRITE
            os.chmod(file_path, new_mode)
        except Exception as e:
            logger.warning(f"Could not remove read-only flag from {file_path}: {e}")

    def __run_preprocessors(self, image_path: Path) -> Dict[FactType, Any]:
        facts: Dict[FactType, Any] = {}
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                result = preprocessor.process(image_path, facts)
                if result:
                    facts.update(result)
        return facts

    def __get_target_path(
        self, file_path: Path, facts: Dict[FactType, Any], claimed_paths: Set[Path]
    ) -> Optional[Path]:
        date = facts.get(FactType.TAKEN_TIMESTAMP)

        if not date:
            date = ExifData.extract_date(file_path)
        if not date:
            self.report.log(SkippedReportItem(file_path, "No date found"))
            return None

        return self.__assign_target_path(date, file_path, claimed_paths)

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

    def __move_photo(self, file_path: Path, target_path: Path) -> None:
        if not self.dry_run:
            shutil.move(file_path, target_path)

        self.report.log(MoveReportItem(file_path, target_path))

    def __run_postprocessors(self, target_path: Path, facts: Dict[FactType, Any]):
        for postprocessor in self.postprocessors:
            if not postprocessor.can_handle(target_path):
                logger.warning(
                    f"{postprocessor.__class__.__name__}: Skipping {target_path}"
                )
                continue
            result = postprocessor.process(target_path, facts)
            if result:
                facts.update(result)

    def __write_report(self):
        report_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.user_data_path / "reports" / f"{report_name}.html"
        self.report.create_report(report_path, self.dry_run)

        if self.open_report:
            self.report.open()
