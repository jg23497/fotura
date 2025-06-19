from pathlib import Path
from datetime import datetime
import logging
import shutil

from photo_tidy.reporting.report import Report
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.skipped_report_item import SkippedReportItem
from photo_tidy.preprocessors.whatsapp_preprocessor import WhatsAppPreprocessor
from photo_tidy.exif_utils import ExifDateExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhotoSorter:

    def __init__(self, input_path: Path, target_root: Path, dry_run: bool = False):
        self.input_path = input_path
        self.target_root = target_root
        self.preprocessors = [WhatsAppPreprocessor(dry_run=dry_run)]
        self.dry_run = dry_run
        self.report = Report()

    def get_photo_date(self, image_path: Path) -> datetime:
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                date = preprocessor.process(image_path)
                if date:
                    return date

        return ExifDateExtractor.extract_date(image_path)

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
                self.report.log_specific(
                    SkippedReportItem(
                        file_path, f"{file_extension} not in supported file extensions"
                    )
                )
                continue

            yield file_path

    def process_photos(self):
        logger.info(f"Processing photos in {self.input_path}")
        logger.info(f"Target root directory: {self.target_root}")
        if self.dry_run:
            logger.info("Running in dry-run mode - no files will be moved")

        for file_path in self._find_photos():
            date = self.get_photo_date(file_path)
            if date:
                target_path = self.get_target_path(date, file_path)
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] {file_path} => {target_path}")
                    else:
                        shutil.move(file_path, target_path)
                        logger.info(f"Moved {file_path} to {target_path}")
                    self.report.log_specific(MoveReportItem(file_path, target_path))
                except Exception as e:
                    logger.error(f"Error moving {file_path}: {str(e)}")
            else:
                logger.warning(f"{file_path}: No date found, skipping")

        logger.info("Report:")
        for report_item in self.report.get_report():
            logger.info(report_item)
        self.report.create_report(Path("output/report.html"))
