import datetime
from pathlib import Path
from unittest.mock import patch

from photo_tidy.preprocessors.filename_timestamp_extract_preprocessor import (
    FilenameTimestampExtractPreprocessor,
)
from photo_tidy.exif_data import ExifData
from photo_tidy.preprocessors.fact_type import FactType


# can_handle


def test_can_handle_accepts_whatsapp_filename():
    processor = FilenameTimestampExtractPreprocessor()
    assert processor.can_handle(Path("IMG-20200101-WA1234.jpg")) is True


def test_can_handle_accepts_android_filename():
    processor = FilenameTimestampExtractPreprocessor()
    assert processor.can_handle(Path("IMG_20200101_123456.jpg")) is True


def test_can_handle_rejects_other_filenames():
    processor = FilenameTimestampExtractPreprocessor()
    assert processor.can_handle(Path("holiday.jpg")) is False


# process


def test_process_extracts_whatsapp_photo_timestamp():
    processor = FilenameTimestampExtractPreprocessor(dry_run=True)
    result = processor.process(Path("IMG-20211225-WA9999.jpg"))

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    assert result[FactType.TAKEN_TIMESTAMP] == datetime.datetime(2021, 12, 25, 12, 0, 0)


def test_process_extracts_android_photo_timestamp():
    processor = FilenameTimestampExtractPreprocessor(dry_run=True)

    result = processor.process(Path("IMG_20211225_123456.jpg"))

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    assert result[FactType.TAKEN_TIMESTAMP] == datetime.datetime(
        2021, 12, 25, 12, 34, 56
    )


def test_process_returns_none_for_unhandled_filename():
    processor = FilenameTimestampExtractPreprocessor(dry_run=True)

    assert processor.process(Path("foobar.jpg")) is None


def test_process_skips_exif_writing_when_dry_run_is_used():
    processor = FilenameTimestampExtractPreprocessor(dry_run=True)

    with patch.object(ExifData, "write_date") as mock:
        result = processor.process(Path("IMG-20220101-WA0001.jpg"))

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    mock.assert_not_called()


def test_process_non_dry_run_writes_exif():
    processor = FilenameTimestampExtractPreprocessor(dry_run=False)
    filename = Path("IMG-20220101-WA0001.jpg")

    with patch.object(ExifData, "write_date") as mock:
        result = processor.process(filename)

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    mock.assert_called_once_with(filename, datetime.datetime(2022, 1, 1, 12, 0, 0))
