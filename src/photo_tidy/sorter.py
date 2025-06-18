from pathlib import Path
from datetime import datetime
import piexif
import logging
import shutil

from photo_tidy.reporting import Report
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.skipped_report_item import SkippedReportItem
from .whatsapp_preprocessor import WhatsAppPreprocessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhotoSorter:
    """Handles the sorting of photos."""

    def __init__(self, input_path: Path, target_root: Path, dry_run: bool = False):
        """Initialize the photo sorter with the input directory path.

        Args:
            input_path (Path): Path to the directory containing photos to sort
            target_root (Path): Path to the root directory where photos will be organized
            dry_run (bool): If True, only show what would be done without making changes
        """
        self.input_path = input_path
        self.target_root = target_root
        self.preprocessors = [WhatsAppPreprocessor(dry_run=dry_run)]
        self.dry_run = dry_run
        self.report = Report()

    def get_photo_date(self, image_path: Path) -> datetime:
        """Extract the date from a photo using preprocessors or EXIF data.

        Args:
            image_path (Path): Path to the photo file

        Returns:
            datetime: The date the photo was taken, or None if not found
        """
        # First try preprocessors
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(image_path):
                date = preprocessor.process(image_path)

        # If no preprocessor handled it, try EXIF data
        try:
            exif_dict = piexif.load(str(image_path))

            # Try different EXIF date fields in order of preference
            date_fields = [
                (piexif.ExifIFD.DateTimeOriginal, "Exif"),
                (piexif.ExifIFD.DateTimeDigitized, "Exif"),
                (piexif.ImageIFD.DateTime, "0th"),
            ]

            for field, ifd in date_fields:
                if ifd in exif_dict and field in exif_dict[ifd]:
                    date_str = exif_dict[ifd][field].decode("utf-8")
                    try:
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue

            logger.warning(f"No EXIF date found in {image_path}")
            return None

        except Exception as e:
            logger.error(f"Error reading EXIF data from {image_path}: {str(e)}")
            return None

    def get_target_path(self, date: datetime, original_path: Path) -> Path:
        """Get the target path for a photo based on its date.

        Args:
            date (datetime): The date the photo was taken
            original_path (Path): The original path of the photo

        Returns:
            Path: The target path where the photo should be copied
        """
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
        """Generator that yields photo files recursively from the input directory.

        Yields:
            Path: Path to each photo file found
        """
        # Supported image extensions
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
        """Process and sort the photos in the input directory.

        Extracts dates from photos and copies them to appropriate year/month directories.
        Recursively processes all subdirectories.
        """
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
