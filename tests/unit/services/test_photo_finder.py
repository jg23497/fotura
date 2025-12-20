from pathlib import Path

import pytest

from fotura.reporting import Report, SkippedReportItem
from fotura.services.photo_finder import PhotoFinder

# Fixtures


@pytest.fixture
def input_dir(fs) -> Path:
    directory = Path("~/input")
    fs.create_dir(directory)
    return directory


@pytest.fixture
def report():
    return Report()


@pytest.fixture
def finder(input_dir, report):
    return PhotoFinder(input_dir, report)


# find_photos


@pytest.mark.parametrize("extension", ["jpg", "jpeg", "tif", "tiff", "arw"])
def test_find_photos_finds_files_with_supported_extensions(
    finder, input_dir, extension
):
    file_path = create_path(input_dir / f"test.{extension}")

    files = list(finder.find_photos())

    assert len(files) == 1
    assert files[0] == file_path


@pytest.mark.parametrize("extension", ["png", "gif", "mp4", "txt", ""])
def test_find_photos_skips_files_with_unsupported_extensions(
    finder, report, input_dir, extension
):
    file_path = create_path(
        input_dir / f"test.{extension}" if extension else input_dir / "test"
    )

    files = list(finder.find_photos())

    assert len(files) == 0
    skipped = [i for i in report.get_report() if type(i) is SkippedReportItem]
    assert len(skipped) == 1
    assert str(file_path) in str(skipped[0])


def test_find_photos_locates_images_under_nested_directories(finder, input_dir):
    root_file = create_path(input_dir / "root.jpg")
    subdir = create_path(input_dir / "subdir", is_dir=True)
    sub_file = create_path(subdir / "sub.jpg")
    nested_dir = create_path(subdir / "nested", is_dir=True)
    nested_file = create_path(nested_dir / "nested.jpg")

    files = list(finder.find_photos())

    assert len(files) == 3
    assert root_file in files
    assert sub_file in files
    assert nested_file in files


def test_find_photos_skips_empty_directories(finder, input_dir):
    jpg_file = create_path(input_dir / "test.jpg")
    subdir = create_path(input_dir / "subdir", is_dir=True)

    files = list(finder.find_photos())

    assert len(files) == 1
    assert jpg_file in files
    assert subdir not in files


def test_find_photos_uses_case_insensitive_extension_matching(finder, input_dir):
    upper_file = create_path(input_dir / "test.JPG")
    lower_file = create_path(input_dir / "test.jpg")

    files = list(finder.find_photos())

    assert len(files) == 2
    assert upper_file in files
    assert lower_file in files


def test_find_photos_handles_empty_directories(finder):
    files = list(finder.find_photos())

    assert len(files) == 0


def create_path(path, is_dir=False, content=b"fake"):
    if is_dir:
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return path
