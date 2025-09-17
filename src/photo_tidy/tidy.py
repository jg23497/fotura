from pathlib import Path, PosixPath
from datetime import datetime
import sys
from typing import Optional, List, Dict, Any, Tuple
import logging
import shutil

from photo_tidy.preprocessors.fact_type import FactType
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.reporting.initialize_report_item import InitializeReportItem
from photo_tidy.reporting.report import Report
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.skipped_report_item import SkippedReportItem
from photo_tidy.reporting.failed_report_item import FailedReportItem
from photo_tidy.exif_utils import ExifDateExtractor

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
    ):
        self.input_path = input_path
        self.target_root = target_root
        self.preprocessors = []
        self.postprocessors = []
        self.report = Report()

        if enabled_preprocessors:
            for preprocessor_name in enabled_preprocessors:
                processor_name = preprocessor_name[0]
                processor_args = preprocessor_name[1]
                if processor_name in PREPROCESSOR_MAP:
                    self.preprocessors.append(
                        PREPROCESSOR_MAP[processor_name](
                            dry_run=dry_run, **processor_args
                        )
                    )
                else:
                    logger.error(f"Unknown preprocessor: {processor_name}")
                    sys.exit(1)

        if enabled_postprocessors:
            for postprocessor_name in enabled_postprocessors:
                processor_name = postprocessor_name[0]
                processor_args = postprocessor_name[1]
                if processor_name in POSTPROCESSOR_MAP:
                    postprocessor_instance = POSTPROCESSOR_MAP[processor_name](
                        self.report, dry_run=dry_run, **processor_args
                    )
                    postprocessor_instance.set_up()
                    self.postprocessors.append(postprocessor_instance)
                else:
                    logger.error(f"Unknown postprocessor: {processor_name}")
                    sys.exit(1)

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
                    date = ExifDateExtractor.extract_date(file_path)
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

        self.report.create_report(Path("output/report.html"), self.dry_run)

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
