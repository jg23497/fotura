import datetime
from pathlib import Path

import piexif
import pytest

from fotura.exif_data import ExifData
from tests.helpers.helper import assert_exif_dates, temporary_images

# extract_date


def test_extract_date_extracts_date_from_datetime_original():
    with temporary_images(["Canon_40D.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        date = ExifData.extract_date(input_image_paths[0])
        assert date == datetime.datetime(2008, 5, 30, 15, 56, 1)


def test_extract_date_extracts_date_from_datetime_digitized():
    with temporary_images(["date-time-digitized-only.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        date = ExifData.extract_date(input_image_paths[0])
        assert date == datetime.datetime(2011, 12, 13, 14, 15, 16)


def test_extract_date_extracts_date_from_datetime():
    with temporary_images(["date-time-only.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        date = ExifData.extract_date(input_image_paths[0])
        assert date == datetime.datetime(2011, 12, 13, 14, 15, 16)


def test_extract_date_returns_none_if_file_not_found():
    non_existent_file = Path("foobar.jpg")

    date = ExifData.extract_date(non_existent_file)

    assert date is None


def test_extract_date_returns_none_if_no_exif_data_found(tmp_path):
    image_path = tmp_path / "blank.jpg"
    image_path.write_bytes(b"foobar")

    date = ExifData.extract_date(image_path)

    assert date is None


def test_extract_date_returns_none_if_invalid_date_format():
    with temporary_images(["no-date.jpg"]) as (_, _, input_image_paths):
        exif = piexif.load(str(input_image_paths[0]))
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = b"invalid-date-format"
        piexif.insert(piexif.dump(exif), str(input_image_paths[0]))

        date = ExifData.extract_date(input_image_paths[0])

        assert date is None


# write_date


def test_write_date_updates_all_exif_date_fields():
    with temporary_images(["no-date.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        exif_dict = piexif.load(str(input_image_paths[0]))

        for location, tag in [
            ("Exif", piexif.ExifIFD.DateTimeOriginal),
            ("Exif", piexif.ExifIFD.DateTimeDigitized),
            ("0th", piexif.ImageIFD.DateTime),
        ]:
            assert tag not in exif_dict[location]

        new_date = datetime.datetime(2011, 12, 13, 14, 15, 16)

        ExifData.write_date(input_image_paths[0], new_date)

        assert_exif_dates(input_image_paths[0], "2011:12:13 14:15:16")


def test_write_date_raises_FileNotFoundError_for_when_file_does_not_exist(tmp_path):
    non_existent_file = tmp_path / "missing.jpg"

    with pytest.raises(FileNotFoundError):
        ExifData.write_date(non_existent_file, datetime.datetime.now())
