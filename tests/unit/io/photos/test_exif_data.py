import datetime
from pathlib import Path

import piexif
import pytest

from fotura.domain.photo import Photo
from fotura.io.photos.exif_data import ExifData
from tests.helpers.helper import assert_exif_dates, temporary_images


@pytest.fixture
def photo(fs, input_path):
    test_image_path = input_path / Path("test_image.jpg")
    fs.create_file(test_image_path, contents=b"image")
    return Photo(test_image_path)


# extract_date


def test_extract_date_extracts_date_from_datetime_original():
    with temporary_images(["Canon_40D.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        photo = Photo(input_image_paths[0])
        date = ExifData.extract_date(photo)
        assert date == datetime.datetime(2008, 5, 30, 15, 56, 1)


def test_extract_date_extracts_date_from_datetime_digitized():
    with temporary_images(["date-time-digitized-only.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        photo = Photo(input_image_paths[0])
        date = ExifData.extract_date(photo)
        assert date == datetime.datetime(2011, 12, 13, 14, 15, 16)


def test_extract_date_extracts_date_from_datetime():
    with temporary_images(["date-time-only.jpg"]) as (
        _,
        _,
        input_image_paths,
    ):
        photo = Photo(input_image_paths[0])
        date = ExifData.extract_date(photo)
        assert date == datetime.datetime(2011, 12, 13, 14, 15, 16)


def test_extract_date_returns_none_if_file_not_found():
    non_existent_file = Path("foobar.jpg")
    photo = Photo(non_existent_file)

    date = ExifData.extract_date(photo)

    assert date is None


def test_extract_date_returns_none_if_no_exif_data_found(tmp_path):
    image_path = tmp_path / "blank.jpg"
    image_path.write_bytes(b"foobar")
    photo = Photo(image_path)

    date = ExifData.extract_date(photo)

    assert date is None


def test_extract_date_returns_none_if_invalid_date_format():
    with temporary_images(["no-date.jpg"]) as (_, _, input_image_paths):
        exif = piexif.load(str(input_image_paths[0]))
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = b"invalid-date-format"
        piexif.insert(piexif.dump(exif), str(input_image_paths[0]))

        photo = Photo(input_image_paths[0])
        date = ExifData.extract_date(photo)

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

        photo = Photo(input_image_paths[0])
        ExifData.write_date(photo, new_date)

        assert_exif_dates(input_image_paths[0], "2011:12:13 14:15:16")


def test_write_date_raises_FileNotFoundError_for_when_file_does_not_exist(tmp_path):
    non_existent_file = tmp_path / "missing.jpg"

    photo = Photo(non_existent_file)
    with pytest.raises(FileNotFoundError):
        ExifData.write_date(photo, datetime.datetime.now())
