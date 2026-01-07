import os
import stat
from pathlib import Path

import pytest

from fotura.domain.photo import Photo
from fotura.io.files import Files
from fotura.reporting import MoveReportItem, Report


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
def photo(fs, input_path):
    test_image_path = input_path / Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"image")
    return Photo(test_image_path)


@pytest.fixture
def report():
    return Report()


@pytest.fixture
def files(request, report):
    dry_run = request.param
    return Files(report, dry_run)


# move


@pytest.mark.parametrize("files", [False], indirect=True)
def test_move_moves_file_to_target_path(files, photo, input_path, target_path):
    files.move(photo, target_path)

    source_path = input_path / Path("test_image.jpg")
    moved = target_path / Path("test_image.jpg")

    assert not source_path.exists()
    assert moved.exists()


@pytest.mark.parametrize("files", [False, True], indirect=True)
def test_move_logs_moved_report_entry(files, photo, target_path, report):
    files.move(photo, target_path)

    moved_items = list(
        item for item in report.get_report() if type(item) is MoveReportItem
    )

    assert len(moved_items) == 1
    assert moved_items[0].source == "~/Desktop/test_image.jpg"
    assert moved_items[0].destination == "~/Pictures/2024/12/31"


@pytest.mark.parametrize("files", [True], indirect=True)
def test_move_skips_move_when_dry_run_mode_is_enabled(
    files, photo, input_path, target_path
):
    files.move(photo, target_path)

    source_path = input_path / Path("test_image.jpg")
    moved = target_path / Path("test_image.jpg")

    assert source_path.exists()
    assert not moved.exists()


# ensure_writable


@pytest.mark.parametrize("files", [False], indirect=True)
def test_ensure_writable_makes_readonly_files_writable_when_dry_run_is_false(
    files, photo
):
    os.chmod(photo.path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    initial_mode = photo.path.stat().st_mode
    assert not (initial_mode & stat.S_IWRITE), "File should start as read-only"

    files.ensure_writable(photo)

    file_mode = photo.path.stat().st_mode
    assert file_mode & stat.S_IWRITE, (
        "File should have write permissions (read-only flag should have been removed)"
    )


@pytest.mark.parametrize("files", [True], indirect=True)
def test_ensure_writable_skips_permission_modification_when_dry_run_is_true(
    files, photo
):
    os.chmod(photo.path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    initial_mode = photo.path.stat().st_mode
    assert not (initial_mode & stat.S_IWRITE), "File should start as read-only"

    files.ensure_writable(photo)

    file_mode = photo.path.stat().st_mode
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
