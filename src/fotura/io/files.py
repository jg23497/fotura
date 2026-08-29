import errno
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
            try:
                shutil.move(media_file.path, target_path)
            except OSError as error:
                self.__handle_move_error(error, target_path)
            media_file.path = target_path

        media_file.log(logging.INFO, "Moved to %s", target_path)

    def ensure_sufficient_space(
        self, media_files: list[MediaFile], target_root: Path
    ) -> None:
        required_space = sum(
            media_file.path.stat().st_size for media_file in media_files
        )
        disk_usage = shutil.disk_usage(self.__existing_parent(target_root))
        available_space = disk_usage.free
        required_space_display = self.__format_size(required_space)
        available_space_display = self.__format_size(available_space)
        percent_full = (
            disk_usage.used / disk_usage.total * 100 if disk_usage.total else 0
        )
        logger.info(
            "Disk space check: %s required, %s available (%.1f%% full)",
            required_space_display,
            available_space_display,
            percent_full,
        )
        if required_space > available_space:
            raise OSError(
                errno.ENOSPC,
                "Not enough disk space to import files: "
                f"{required_space_display} required, "
                f"{available_space_display} available",
                str(target_root),
            )

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

    @staticmethod
    def __handle_move_error(error: OSError, target_path: Path) -> None:
        if error.errno == errno.ENOSPC:
            raise OSError(
                errno.ENOSPC,
                "Ran out of disk space while moving files",
                str(target_path),
            ) from error
        raise error

    @staticmethod
    def __format_size(size_in_bytes: int) -> str:
        bytes_per_megabyte = 1024**2
        bytes_per_gigabyte = 1024**3
        if size_in_bytes >= bytes_per_gigabyte:
            return f"{size_in_bytes / bytes_per_gigabyte:.2f} GB"
        return f"{size_in_bytes / bytes_per_megabyte:.2f} MB"

    @staticmethod
    def __existing_parent(path: Path) -> Path:
        candidate = path
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        return candidate
