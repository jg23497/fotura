import contextlib
from os import scandir
from pathlib import Path
import shutil
import tempfile

import piexif


@contextlib.contextmanager
def temporary_image(test_image_filename):
    with __temporary_image_directory() as (input_temp_dir, target_root):
        image_path = __get_test_data_directory() / test_image_filename
        copied_img = input_temp_dir / image_path.name
        shutil.copy2(image_path, copied_img)

        yield input_temp_dir, target_root, copied_img


@contextlib.contextmanager
def temporary_images():
    with __temporary_image_directory() as (input_temp_dir, target_root):
        shutil.copytree(__get_test_data_directory(), input_temp_dir, dirs_exist_ok=True)
        yield input_temp_dir, target_root


def get_all_files(path="."):
    with scandir(path) as entries:
        for entry in entries:
            if entry.is_file():
                yield (entry.path)
            elif entry.is_dir():
                yield from get_all_files(entry.path)


def verify_exif_dates(image_path, expected_date_str):
    """Verify that an image has the correct EXIF date metadata.

    Args:
        image_path: Path to the image file
        expected_date_str: Expected date string in format "YYYY:MM:DD HH:MM:SS"
    """
    exif_dict = piexif.load(str(image_path))

    for location, tag in [
        ("Exif", piexif.ExifIFD.DateTimeOriginal),
        ("Exif", piexif.ExifIFD.DateTimeDigitized),
        ("0th", piexif.ImageIFD.DateTime),
    ]:
        date_str = exif_dict[location][tag].decode("utf-8")
        assert date_str == expected_date_str


@contextlib.contextmanager
def __temporary_image_directory():
    with (
        tempfile.TemporaryDirectory() as input_temp_dir,
        tempfile.TemporaryDirectory() as target_temp_dir,
    ):
        input_path = Path(input_temp_dir)
        target_root = Path(target_temp_dir)

        yield input_path, target_root


def __get_test_data_directory() -> Path:
    test_directory = Path(__file__).resolve().parent.parent
    return test_directory / "data"
