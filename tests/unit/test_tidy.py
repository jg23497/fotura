import contextlib
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from photo_tidy.exif_utils import ExifDateExtractor
from photo_tidy.preprocessors.fact_type import FactType
from photo_tidy.reporting.failed_report_item import FailedReportItem
from photo_tidy.reporting.report import Report
from photo_tidy.reporting.skipped_report_item import SkippedReportItem
from photo_tidy.tidy import Tidy


# Test helpers


@contextlib.contextmanager
def image_context(test_image_filename):
    test_dir = Path(__file__).resolve().parent.parent
    data_dir = test_dir / "data"

    with (
        tempfile.TemporaryDirectory() as input_temp_dir,
        tempfile.TemporaryDirectory() as target_temp_dir,
    ):
        input_path = Path(input_temp_dir)
        target_root = Path(target_temp_dir)

        image_path = data_dir / test_image_filename
        copied_img = input_path / image_path.name
        shutil.copy2(image_path, copied_img)

        yield input_path, target_root, copied_img


class DummyPreprocessor:
    def __init__(
        self,
        *,
        dry_run: bool = False,
        can_handle: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.can_handle: Mock = Mock(return_value=can_handle)
        self.process: Mock = Mock(return_value={})


class DummyPreprocessorOther:
    def __init__(
        self,
        *,
        dry_run: bool = False,
        can_handle: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.can_handle: Mock = Mock(return_value=can_handle)
        self.process: Mock = Mock(return_value={})


class DummyPostprocessor:
    def __init__(self, report: Report, *, dry_run: bool = False) -> None:
        self.report = report
        self.dry_run = dry_run
        self.set_up = Mock()
        self.process: Mock = Mock()


# Fixtures


@pytest.fixture
def input_dir(fs) -> Path:
    directory = Path("~/input")
    fs.create_dir(directory)
    return directory


@pytest.fixture
def target_root(fs) -> Path:
    directory = Path("~/target")
    fs.create_dir(directory)
    return directory


@pytest.fixture(autouse=True)
def stub_report_template():
    with patch.object(Report, "create_report", return_value="<html></html>"):
        yield


# Tests
# Processor initialization


@patch("photo_tidy.tidy.PREPROCESSOR_MAP", {"dummy_preprocessor": DummyPreprocessor})
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_preprocessors(input_dir, target_root, dry_run):
    tidy = Tidy(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_preprocessors=[("dummy_preprocessor", {})],
    )

    assert len(tidy.preprocessors) == 1
    assert isinstance(tidy.preprocessors[0], DummyPreprocessor)
    assert tidy.preprocessors[0].dry_run is dry_run


@patch("photo_tidy.tidy.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_postprocessors(input_dir, target_root, dry_run):
    tidy = Tidy(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_postprocessors=[("dummy_postprocessor", {})],
    )

    assert len(tidy.postprocessors) == 1
    assert isinstance(tidy.postprocessors[0], DummyPostprocessor)
    assert tidy.postprocessors[0].dry_run is dry_run


@patch("photo_tidy.tidy.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
def test_calls_setup_on_postprocessors(input_dir, target_root):
    tidy = Tidy(
        input_path=input_dir,
        target_root=target_root,
        enabled_preprocessors=[],
        enabled_postprocessors=[("dummy_postprocessor", {})],
    )

    assert tidy.postprocessors[0].set_up.called


@patch("photo_tidy.tidy.PREPROCESSOR_MAP", {})
@patch("photo_tidy.tidy.POSTPROCESSOR_MAP", {})
def test_exits_when_unknown_preprocessor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Tidy(
            input_path=input_dir,
            target_root=target_root,
            enabled_preprocessors=[("foobar", {})],
        )


@patch("photo_tidy.tidy.PREPROCESSOR_MAP", {})
@patch("photo_tidy.tidy.POSTPROCESSOR_MAP", {})
def test_exits_when_unknown_postprocessor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Tidy(
            input_path=input_dir,
            target_root=target_root,
            enabled_postprocessors=[("foobar", {})],
        )


## process_photos


@patch(
    "photo_tidy.tidy.PREPROCESSOR_MAP",
    {"foo": DummyPreprocessor, "bar": DummyPreprocessorOther},
)
def test_last_preprocessor_fact_takes_precedence(input_dir, target_root):
    image_path = input_dir / "img.jpg"
    image_path.write_bytes(b"foo")

    tidy = Tidy(
        input_path=input_dir,
        target_root=target_root,
        enabled_preprocessors=[
            ("foo", {}),
            ("bar", {}),
        ],
    )

    tidy.preprocessors[0].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2021, 1, 2, 3, 4, 5)
    }
    tidy.preprocessors[1].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2020, 1, 2, 3, 4, 5)
    }

    tidy.process_photos()

    dest_dir = target_root / "2020" / "2020-01"
    expected_path = dest_dir / image_path.name
    assert expected_path.exists()
    assert not image_path.exists()


@patch(
    "photo_tidy.tidy.PREPROCESSOR_MAP",
    {"processor": DummyPreprocessor},
)
def test_process_photos_ignores_exif_data_when_processor_sourced_timestamp_is_obtained():
    with image_context("IMG_20100102_030405.jpg") as (
        input_path,
        target_root,
        image_path,
    ):
        tidy = Tidy(
            input_path=input_path,
            target_root=target_root,
            enabled_preprocessors=[
                ("processor", {}),
            ],
        )

        tidy.preprocessors[0].process.return_value = {
            FactType.TAKEN_TIMESTAMP: datetime(2010, 1, 2, 3, 4, 5)
        }

        tidy.process_photos()

        dest_dir = target_root / "2010" / "2010-01"
        expected_path = dest_dir / image_path.name
        date = ExifDateExtractor.extract_date(expected_path)

        assert date is not None
        assert date.year == 2025
        assert expected_path.exists()
        assert not image_path.exists()


@pytest.mark.parametrize("extension", ["jpg", "jpeg", "tif", "tiff", "arw"])
def test_process_photos_handles_files_with_supported_extensions(
    input_dir, target_root, extension
):
    tidy = Tidy(input_path=input_dir, target_root=target_root)

    file_path = input_dir / f"foo.{extension}"
    file_path.write_bytes(b"bar")

    with patch.object(
        ExifDateExtractor, "extract_date", Mock(return_value=datetime(2020, 1, 1))
    ):
        tidy.process_photos()

    assert not file_path.exists()
    assert (target_root / "2020" / "2020-01" / f"foo.{extension}").exists()


@pytest.mark.parametrize("extension", ["mp4", "txt", ""])
def test_process_photos_skips_unsupported_files(input_dir, target_root, extension):
    tidy = Tidy(input_path=input_dir, target_root=target_root)

    file_path = input_dir / f"foo.{extension}"
    file_path.write_text("bar")

    tidy.process_photos()

    assert file_path.exists()
    skipped = [i for i in tidy.report.get_report() if i.name() == "Skipped"]
    assert len(skipped) == 1
    assert str(file_path) in str(skipped[0])


def test_process_photos_moves_files_and_runs_postprocessors():
    with image_context("IMG_20240909_103402.jpg") as (
        input_path,
        target_root,
        image_path,
    ):
        tidy = Tidy(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )
        tidy.process_photos()

        dest_dir = target_root / "2024" / "2024-09"
        moved = dest_dir / image_path.name
        assert moved.exists()
        assert not image_path.exists()

        names = [item.name() for item in tidy.report.get_report()]
        assert "Moved" in names

        assert Path("output/report.html").exists()


def test_process_photos_skips_when_a_timestamp_cannot_be_obtained():
    with image_context("no-date.jpg") as (
        input_path,
        target_root,
        image_path,
    ):
        tidy = Tidy(
            input_path=input_path,
            target_root=target_root,
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )
        tidy.process_photos()

        skipped_item = next(
            (
                item
                for item in tidy.report.get_report()
                if type(item) is SkippedReportItem
            )
        )
        assert skipped_item
        assert "no-date.jpg" in skipped_item.__repr__()
        assert image_path.exists()


@patch.object(shutil, "move", side_effect=ValueError)
def test_process_photos_logs_failed_on_move_exception(mock_move):
    with image_context("Canon_40D.jpg") as (
        input_path,
        target_root,
        image_path,
    ):
        tidy = Tidy(
            input_path=input_path,
            target_root=target_root,
        )

        tidy.process_photos()

        failed_item = next(
            (
                item
                for item in tidy.report.get_report()
                if type(item) is FailedReportItem
            )
        )
        assert failed_item
        assert "Canon_40D.jpg" in failed_item.__repr__()
        assert image_path.exists()


def test_process_photos_handles_filename_collisions_using_increment_strategy():
    with image_context("Canon_40D.jpg") as (
        input_path,
        target_root,
        image_path,
    ):
        target_dir = target_root / "2008" / "2008-05"
        os.makedirs(target_dir)
        shutil.copy(image_path, target_dir)

        tidy = Tidy(
            input_path=input_path,
            target_root=target_root,
        )

        tidy.process_photos()

        assert not image_path.exists()
        assert (target_dir / "Canon_40D.jpg").exists()
        assert (target_dir / "Canon_40D_1.jpg").exists()
