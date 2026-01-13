import datetime
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fotura.io.photos.exif_data import ExifData
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.processors.preprocessors.filename_timestamp_extract_preprocessor import (
    FilenameTimestampExtractPreprocessor,
)

# Fixtures


@pytest.fixture
def processor():
    context = Context(user_config_path=Path(tempfile.mkdtemp()), dry_run=False)
    return FilenameTimestampExtractPreprocessor(context)


@pytest.fixture
def processor_dry_run():
    context = Context(user_config_path=Path(tempfile.mkdtemp()), dry_run=True)
    return FilenameTimestampExtractPreprocessor(context)


# can_handle


def test_can_handle_accepts_whatsapp_filename(processor):
    assert processor.can_handle(Path("IMG-20200101-WA1234.jpg")) is True


def test_can_handle_accepts_android_filename(processor):
    assert processor.can_handle(Path("IMG_20200101_123456.jpg")) is True


def test_can_handle_rejects_other_filenames(processor):
    assert processor.can_handle(Path("holiday.jpg")) is False


# process


def test_process_extracts_whatsapp_photo_timestamp(processor_dry_run):
    result = processor_dry_run.process(Path("IMG-20211225-WA9999.jpg"), {})

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    assert result[FactType.TAKEN_TIMESTAMP] == datetime.datetime(2021, 12, 25, 12, 0, 0)


def test_process_extracts_android_photo_timestamp(processor_dry_run):
    result = processor_dry_run.process(Path("IMG_20211225_123456.jpg"), {})

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    assert result[FactType.TAKEN_TIMESTAMP] == datetime.datetime(
        2021, 12, 25, 12, 34, 56
    )


def test_process_returns_none_for_unhandled_filename(processor_dry_run):
    assert processor_dry_run.process(Path("foobar.jpg"), {}) is None


def test_process_skips_exif_writing_when_dry_run_is_used(processor_dry_run):
    with patch.object(ExifData, "write_date") as mock:
        result = processor_dry_run.process(Path("IMG-20220101-WA0001.jpg"), {})

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    mock.assert_not_called()


def test_process_writes_exif_date_data_when_dry_run_is_not_used(processor):
    filename = Path("IMG-20220101-WA0001.jpg")

    with patch.object(ExifData, "write_date") as mock:
        result = processor.process(filename, {})

    assert result is not None
    assert FactType.TAKEN_TIMESTAMP in result
    mock.assert_called_once_with(filename, datetime.datetime(2022, 1, 1, 12, 0, 0))
