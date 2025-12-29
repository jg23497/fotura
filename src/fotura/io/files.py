import logging
import os
import shutil
import stat
from pathlib import Path

from fotura.domain.photo import Photo
from fotura.reporting import MoveReportItem, Report

logger = logging.getLogger(__name__)


class Files:
    def __init__(self, report: Report, dry_run: bool):
        self.report = report
        self.dry_run = dry_run

    def move(self, photo: Photo, target_path: Path):
        if not self.dry_run:
            shutil.move(photo.path, target_path)

        self.report.log(MoveReportItem(photo.path, target_path))

    def ensure_writable(self, photo: Photo):
        if self.dry_run:
            return
        try:
            # Windows: ensure FILE_ATTRIBUTE_READONLY is removed.
            # Unix: ensure user-write bit is set.
            current_mode = photo.path.stat().st_mode
            new_mode = current_mode | stat.S_IWRITE
            os.chmod(photo.path, new_mode)
        except Exception as e:
            logger.warning(f"Could not remove read-only flag from {photo.path}: {e}")
