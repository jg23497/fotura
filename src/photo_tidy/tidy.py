from pathlib import Path, PosixPath
from datetime import datetime
import sys
from typing import Optional, List, Dict, Any, Tuple
import logging
import shutil
from platformdirs import user_config_dir, user_data_dir

from photo_tidy.preprocessors.fact_type import FactType
from photo_tidy.processors.context import Context
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.reporting.initialize_report_item import InitializeReportItem
from photo_tidy.reporting.report import Report
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.skipped_report_item import SkippedReportItem
from photo_tidy.reporting.failed_report_item import FailedReportItem
from photo_tidy.exif_data import ExifData

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
    ):
        self.input_path = input_path
        self.target_root = target_root
        self.preprocessors = []
        self.postprocessors = []
        self.report = Report()
        self.user_config_path = Path(user_config_dir("phototidy"))
        self.user_data_path = Path(user_data_dir("phototidy"))
        self.open_report = open_report
        self.processor_context = Context(report=self.report, dry_run=dry_run)

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

        for file_path in self.__find_photos():
            target_path = PosixPath()

            try:
                facts = self.__run_preprocessors(file_path)
                date = facts.get(FactType.TAKEN_TIMESTAMP)

                if not date:
                    date = ExifData.extract_date(file_path)
                if not date:
                    self.report.log(SkippedReportItem(file_path, "No date found"))
                    continue

                target_path = self.__get_target_path(date, file_path)

                if not self.dry_run:
                    shutil.move(file_path, target_path)
                self.report.log(MoveReportItem(file_path, target_path))

                self.__run_postprocessors(target_path)
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
                instance.set_up()
                processor_instances.append(instance)
            else:
                logger.error(f"Unknown processor: {processor_name}")
                sys.exit(1)

    def __run_preprocessors(self, image_path: Path) -> Dict[FactType, Any]:
        facts: Dict[FactType, Any] = {}
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                result = preprocessor.process(image_path)
                if result:
                    facts.update(result)
        return facts

    def __run_postprocessors(self, target_path: Path):
        for postprocessor in self.postprocessors:
            postprocessor.process(target_path)

    def __get_target_path(self, date: datetime, original_path: Path) -> Path:
        target_dir = self.target_root / str(date.year) / f"{date.year}-{date.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        base_name = original_path.stem
        extension = original_path.suffix
        counter = 1
        target_path = target_dir / f"{base_name}{extension}"

        while target_path.exists():
            target_path = target_dir / f"{base_name}_{counter}{extension}"
            counter += 1

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
