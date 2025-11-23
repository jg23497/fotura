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
from photo_tidy.reporting.failed_report_item import FailedReportItem
from photo_tidy.reporting.initialize_report_item import InitializeReportItem
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.report import Report
from photo_tidy.reporting.skipped_report_item import SkippedReportItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Tidy:
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".tif", ".arw"}

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
        self.preprocessors = []
        self.postprocessors = []
        self.report = Report()
        self.user_config_path = Path(user_config_dir("phototidy"))
        self.user_data_path = Path(user_data_dir("phototidy"))
        self.target_path_format = target_path_format
        self.open_report = open_report

        self.processor_context = Context(
            report=self.report, user_config_path=self.user_config_path, dry_run=dry_run
        )

        self.conflict_resolver = self.__get_conflict_resolver(
            conflict_resolution_strategy
        )

        self.__test_read_write_permissions()

        if enabled_preprocessors:
            self.__configure_processors(
                PREPROCESSOR_MAP, enabled_preprocessors, self.preprocessors
            )
        if enabled_postprocessors:
            self.__configure_processors(
                POSTPROCESSOR_MAP, enabled_postprocessors, self.postprocessors
            )

        self.dry_run = dry_run

    def process_photos(self):
        self.report.log(
            InitializeReportItem(self.dry_run, self.input_path, self.target_root)
        )

        claimed_paths = set()

        for file_path in self.__find_photos():
            target_path = Path()

            try:
                facts = self.__run_preprocessors(file_path)
                date = facts.get(FactType.TAKEN_TIMESTAMP)

                if not date:
                    date = ExifData.extract_date(file_path)
                if not date:
                    self.report.log(SkippedReportItem(file_path, "No date found"))
                    continue

                target_path = self.__get_target_path(date, file_path, claimed_paths)
                if target_path is None:
                    self.report.log(
                        SkippedReportItem(file_path, "Conflict resolution strategy")
                    )
                    continue

                if not self.dry_run:
                    self.__remove_read_only_flag(file_path)
                    shutil.move(file_path, target_path)

                self.report.log(MoveReportItem(file_path, target_path))

                self.__run_postprocessors(target_path, facts)
            except Exception as e:
                self.report.log(FailedReportItem(file_path, target_path, e))
                break

        report_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.user_data_path / "reports" / f"{report_name}.html"
        self.report.create_report(report_path, self.dry_run)

        if self.open_report:
            self.report.open()

    def __configure_processors(
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

    def __run_preprocessors(self, image_path: Path) -> Dict[FactType, Any]:
        facts: Dict[FactType, Any] = {}
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                result = preprocessor.process(image_path, facts)
                if result:
                    facts.update(result)
        return facts

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

    def __get_target_path(
        self, date: datetime, original_path: Path, claimed_paths: Set
    ) -> Path:
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

        claimed_paths.add(target_path)
        return target_path

    def __find_photos(self):
        for file_path in self.input_path.rglob("*"):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in self.SUPPORTED_EXTENSIONS:
                self.report.log(
                    SkippedReportItem(
                        file_path, f"{file_extension} not in supported file extensions"
                    )
                )
                continue

            yield file_path

    def __get_conflict_resolver(self, strategy: str):
        if strategy in STRATEGIES:
            return STRATEGIES[strategy]()
        else:
            raise ValueError(f"Unsupported conflict resolution strategy: {strategy}")

    def __remove_read_only_flag(self, file_path):
        try:
            # Windows: ensure FILE_ATTRIBUTE_READONLY is removed.
            # Unix: ensure user-write bit is set.
            current_mode = file_path.stat().st_mode
            new_mode = current_mode | stat.S_IWRITE
            os.chmod(file_path, new_mode)
        except Exception as e:
            logger.warning(f"Could not remove read-only flag from {file_path}: {e}")

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
