import logging
import os
import shutil
import stat
from pathlib import Path

from fotura.domain.media_file import MediaFile

logger = logging.getLogger(__name__)


class Files:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run

    def move(self, media_file: MediaFile, target_path: Path):
        if not self.dry_run:
            shutil.move(media_file.path, target_path)
            media_file.path = target_path

        media_file.log(logging.INFO, "Moved to %s", target_path)

    def ensure_writable(self, media_file: MediaFile):
        if self.dry_run:
            return
        try:
            # Windows: ensure FILE_ATTRIBUTE_READONLY is removed.
            # Unix: ensure user-write bit is set.
            current_mode = media_file.path.stat().st_mode
            new_mode = current_mode | stat.S_IWRITE
            os.chmod(media_file.path, new_mode)
        except Exception:
            media_file.log(
                logging.WARNING, "Could not remove read-only flag", exc_info=True
            )

    def has_read_write_permissions(self, input_path: Path):
        temp_path = Path(input_path / "permission-check.tmp")

        if not temp_path.exists():
            try:
                with open(temp_path, "w") as f:
                    f.write("test")
            except Exception as e:
                raise PermissionError(
                    f"Permission check: Failed to write test file under {input_path}': {e}"
                ) from e

        try:
            os.remove(temp_path)
        except Exception as e:
            raise PermissionError(
                f"Permission check: Failed to remove test file under '{temp_path}': {e}"
            ) from e

        return True
