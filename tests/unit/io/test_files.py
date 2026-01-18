import logging
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from fotura.domain.media_file import MediaFile
from fotura.io.files import Files
from tests.helpers.helper import get_log_entries


@pytest.fixture
def input_path(fs) -> Path:
    directory = Path("~/Desktop")
    fs.create_dir(directory)
    return directory


@pytest.fixture
def target_path(fs) -> Path:
    directory = Path("~/Pictures/2024/12/31")
    fs.create_dir(directory)
    return directory


@pytest.fixture
def media_file(fs, input_path):
    test_image_path = input_path / Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"image")
    return MediaFile(test_image_path)


@pytest.fixture
def files(request):
    dry_run = request.param
    return Files(dry_run)


# move


@pytest.mark.parametrize("files", [False], indirect=True)
def test_move_moves_file_to_target_path(files, media_file, input_path, target_path):
    new_path = target_path / Path("test_image.jpg")
    files.move(media_file, new_path)

    source_path = input_path / Path("test_image.jpg")

    assert not source_path.exists()
    assert new_path.exists()


@pytest.mark.parametrize("files", [False], indirect=True)
def test_move_updates_photo_path(files, media_file, input_path, target_path):
    new_path = target_path / Path("test_image.jpg")
    files.move(media_file, new_path)

    source_path = input_path / Path("test_image.jpg")

    assert media_file.original_path == source_path
    assert media_file.path == new_path


@pytest.mark.parametrize("files", [False, True], indirect=True)
def test_move_logs_moved_report_entry(files, media_file, target_path, caplog):
    new_path = target_path / Path("test_image.jpg")
    with caplog.at_level(logging.INFO):
        files.move(media_file, new_path)

    log_entries = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.INFO and r.getMessage().startswith("Moved"),
    )

    assert len(log_entries) == 1

    assert str(log_entries[0].media_file) == "~/Desktop/test_image.jpg"
    assert str(new_path) in log_entries[0].getMessage()


@pytest.mark.parametrize("files", [True], indirect=True)
def test_move_skips_move_when_dry_run_mode_is_enabled(
    files, media_file, input_path, target_path
):
    new_path = target_path / Path("test_image.jpg")
    files.move(media_file, target_path)

    source_path = input_path / Path("test_image.jpg")

    assert source_path.exists()
    assert not new_path.exists()


# ensure_writable


@pytest.mark.parametrize("files", [False], indirect=True)
def test_ensure_writable_makes_readonly_files_writable_when_dry_run_is_false(
    files, media_file
):
    os.chmod(media_file.path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    initial_mode = media_file.path.stat().st_mode
    assert not (initial_mode & stat.S_IWRITE), "File should start as read-only"

    files.ensure_writable(media_file)

    file_mode = media_file.path.stat().st_mode
    assert file_mode & stat.S_IWRITE, (
        "File should have write permissions (read-only flag should have been removed)"
    )


@pytest.mark.parametrize("files", [False], indirect=True)
def test_ensure_writable_logs_when_readonly_flag_cannot_be_removed(
    files, media_file, caplog
):
    with patch.object(os, "chmod", side_effect=PermissionError):
        with caplog.at_level(logging.INFO):
            files.ensure_writable(media_file)

    log_entries = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.WARNING
        and "Could not remove read-only flag" in r.getMessage()
        and r.exc_info[0] is PermissionError,
    )

    assert len(log_entries) == 1
    assert str(media_file.path) in str(log_entries[0].media_file)


@pytest.mark.parametrize("files", [True], indirect=True)
def test_ensure_writable_skips_permission_modification_when_dry_run_is_true(
    files, media_file
):
    os.chmod(media_file.path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    initial_mode = media_file.path.stat().st_mode
    assert not (initial_mode & stat.S_IWRITE), "File should start as read-only"

    files.ensure_writable(media_file)

    file_mode = media_file.path.stat().st_mode
    assert file_mode == initial_mode, "File permission should remain unchanged"


# has_read_write_permissions


@pytest.mark.parametrize("files", [True], indirect=True)
def test_has_read_write_permissions_returns_true_when_read_write_permissions_are_present(
    files, input_path
):
    assert files.has_read_write_permissions(input_path)


@pytest.mark.parametrize("files", [True], indirect=True)
def test_has_read_write_permissions_raises_exception_when_read_write_permissions_are_not_present(
    fs, files
):
    tmp_path = Path("~/Desktop")

    if os.name == "nt":
        fs.create_dir(tmp_path, perm_bits=0o444)
    else:
        fs.create_dir(tmp_path, perm_bits=0o555)

    with pytest.raises(
        PermissionError, match="Permission check: Failed to write test file"
    ):
        files.has_read_write_permissions(tmp_path)
