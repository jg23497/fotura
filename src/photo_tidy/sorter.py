from pathlib import Path
from datetime import datetime
import sys
from typing import Optional, List, Dict, Any
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


class PhotoSorter:
    def __init__(
        self,
        input_path: Path,
        target_root: Path,
        dry_run: bool = False,
        enabled_preprocessors: Optional[List[str]] = None,
        enabled_postprocessors: Optional[List[str]] = None,
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

    def run_preprocessors(self, image_path: Path) -> Optional[Dict[FactType, Any]]:
        facts = dict()
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                facts.update(preprocessor.process(image_path))
        return facts

    def run_postprocessors(self, target_path: Path):
        for postprocessor in self.postprocessors:
            postprocessor.process(target_path)

    def get_target_path(self, date: datetime, original_path: Path) -> Path:
        # Create year/month directory structure
        target_dir = self.target_root / str(date.year) / f"{date.year}-{date.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Start with original filename
        base_name = original_path.stem
        extension = original_path.suffix
        counter = 1
        target_path = target_dir / f"{base_name}{extension}"

        # If file exists, append counter until we find an available name
        while target_path.exists():
            target_path = target_dir / f"{base_name}_{counter}{extension}"
            counter += 1

        return target_path

    def _find_photos(self):
        image_extensions = {".jpg", ".jpeg", ".tiff", ".tif"}

        for file_path in self.input_path.rglob("*"):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in image_extensions:
                self.report.log(
                    SkippedReportItem(
                        file_path, f"{file_extension} not in supported file extensions"
                    )
                )
                continue

            yield file_path

    def process_photos(self):
        self.report.log(
            InitializeReportItem(self.dry_run, self.input_path, self.target_root)
        )

        for file_path in self._find_photos():
            facts = self.run_preprocessors(file_path)
            date = facts.get(FactType.TAKEN_TIMESTAMP)
            if not date:
                date = ExifDateExtractor.extract_date(file_path)
            if not date:
                self.report.log(SkippedReportItem(file_path, "No date found"))
                continue

            target_path = self.get_target_path(date, file_path)
            try:
                if not self.dry_run:
                    shutil.move(file_path, target_path)
                self.report.log(MoveReportItem(file_path, target_path))
                self.run_postprocessors(target_path)
            except Exception as e:
                self.report.log(FailedReportItem(file_path, target_path, e))

        self.report.create_report(Path("output/report.html"), self.dry_run)
