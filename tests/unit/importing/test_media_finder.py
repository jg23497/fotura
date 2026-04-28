import logging
from pathlib import Path

import pytest

from fotura.domain.photo import Photo
from fotura.importing.media_finder import MediaFinder
from tests.helpers.helper import get_log_entries

# Fixtures


@pytest.fixture
def input_dir(fs) -> Path:
    directory = Path("~/input")
    fs.create_dir(directory)
    return directory


@pytest.fixture
def finder(input_dir):
    return MediaFinder(input_dir)


# find


@pytest.mark.parametrize(
    "extension",
    [
        "jpg",
        "jpeg",
        "tif",
        "tiff",
        "arw",
        "nef",
        "cr2",
        "orf",
        "pef",
        "dng",
        "raw",
        "raf",
    ],
)
def test_find_finds_files_with_supported_extensions(finder, input_dir, extension):
    file_path = create_path(input_dir / f"test.{extension}")

    photos = list[Photo](finder.find())

    assert len(photos) == 1
    assert photos[0].path == file_path


@pytest.mark.parametrize("extension", ["png", "gif", "mp4", "txt", ""])
def test_find_ignores_files_with_unsupported_extensions(
    finder, input_dir, extension, caplog
):
    file_path = create_path(
        input_dir / f"test.{extension}" if extension else input_dir / "test"
    )

    with caplog.at_level(logging.INFO):
        photos = list[Photo](finder.find())

    log_entries = get_log_entries(
        caplog,
        lambda r: (
            r.levelno == logging.WARNING and r.getMessage().startswith("Ignored")
        ),
    )

    assert len(photos) == 0
    assert len(log_entries) > 0
    assert str(file_path) in log_entries[0].getMessage()


def test_find_locates_images_under_nested_directories(finder, input_dir):
    root_file = create_path(input_dir / "root.jpg")
    subdir = create_path(input_dir / "subdir", is_dir=True)
    sub_file = create_path(subdir / "sub.jpg")
    nested_dir = create_path(subdir / "nested", is_dir=True)
    nested_file = create_path(nested_dir / "nested.jpg")

    photos = finder.find()
    photo_paths = list(map(lambda x: x.path, photos))

    assert len(photo_paths) == 3
    assert root_file in photo_paths
    assert sub_file in photo_paths
    assert nested_file in photo_paths


def test_find_skips_empty_directories(finder, input_dir):
    jpg_file = create_path(input_dir / "test.jpg")
    subdir = create_path(input_dir / "subdir", is_dir=True)

    photos = finder.find()
    photo_paths = list(map(lambda x: x.path, photos))

    assert len(photo_paths) == 1
    assert jpg_file in photo_paths
    assert subdir not in photo_paths


def test_find_uses_case_insensitive_extension_matching(finder, input_dir):
    upper_file = create_path(input_dir / "test.JPG")
    lower_file = create_path(input_dir / "test.jpg")

    photos = finder.find()
    photo_paths = list(map(lambda x: x.path, photos))

    assert len(photo_paths) == 2
    assert upper_file in photo_paths
    assert lower_file in photo_paths


def test_find_handles_empty_directories(finder):
    files = list(finder.find())

    assert len(files) == 0


def create_path(path, is_dir=False, content=b"fake"):
    if is_dir:
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return path
