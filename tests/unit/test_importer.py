import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from fotura.importer import Importer
from fotura.io.photos.exif_data import ExifData
from fotura.preprocessors.fact_type import FactType
from fotura.reporting import (
    FailedReportItem,
    MoveReportItem,
    SkippedReportItem,
)
from tests.helpers import helper
from tests.helpers.helper import (
    temporary_images,
)
from tests.helpers.processors import (
    ComplexDummyPostprocessor,
    DummyPostprocessor,
    DummyPreprocessor,
)

# Fixtures


@pytest.fixture
def input_dir(fs) -> Path:
    directory = Path("~/input")
    fs.create_dir(directory)
    return directory


@pytest.fixture(autouse=True)
def stub_report_template():
    mock_template = Mock()
    mock_template.render.return_value = "<html></html>"
    with patch("jinja2.Environment.get_template", return_value=mock_template):
        yield


# Tests
# Processor initialization


@patch("fotura.importer.PREPROCESSOR_MAP", {"dummy_preprocessor": DummyPreprocessor})
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_preprocessors(input_dir, target_root, dry_run):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_preprocessors=[("dummy_preprocessor", {})],
    )

    assert len(importer.preprocessors) == 1
    assert isinstance(importer.preprocessors[0], DummyPreprocessor)
    assert importer.preprocessors[0].context.dry_run is dry_run


@patch("fotura.importer.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_postprocessors(input_dir, target_root, dry_run):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_postprocessors=[("dummy_postprocessor", {})],
    )

    assert len(importer.postprocessors) == 1
    assert isinstance(importer.postprocessors[0], DummyPostprocessor)
    assert importer.postprocessors[0].context.dry_run is dry_run


@patch("fotura.importer.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
def test_calls_configure_on_postprocessors(input_dir, target_root):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        enabled_preprocessors=[],
        enabled_postprocessors=[("dummy_postprocessor", {})],
    )

    assert importer.postprocessors[0].configure.called


@patch("fotura.importer.PREPROCESSOR_MAP", {})
@patch("fotura.importer.POSTPROCESSOR_MAP", {})
def test_exits_when_unknown_preprocessor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Importer(
            input_path=input_dir,
            target_root=target_root,
            enabled_preprocessors=[("foobar", {})],
        )


@patch("fotura.importer.PREPROCESSOR_MAP", {})
@patch("fotura.importer.POSTPROCESSOR_MAP", {})
def test_exits_when_unknown_postprocessor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Importer(
            input_path=input_dir,
            target_root=target_root,
            enabled_postprocessors=[("foobar", {})],
        )


## process_photos


@patch(
    "fotura.importer.PREPROCESSOR_MAP",
    {"foo": DummyPreprocessor, "bar": DummyPreprocessor},
)
def test_last_preprocessor_fact_takes_precedence(input_dir, target_root):
    image_path = input_dir / "img.jpg"
    image_path.write_bytes(b"foo")

    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        enabled_preprocessors=[
            ("foo", {}),
            ("bar", {}),
        ],
    )

    importer.preprocessors[0].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2021, 1, 2, 3, 4, 5)
    }
    importer.preprocessors[1].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2020, 1, 2, 3, 4, 5)
    }

    importer.process_photos()

    dest_dir = target_root / "2020" / "2020-01"
    expected_path = dest_dir / image_path.name
    assert expected_path.exists()
    assert not image_path.exists()


@patch(
    "fotura.importer.PREPROCESSOR_MAP",
    {"processor": DummyPreprocessor},
)
def test_process_photos_ignores_exif_data_when_processor_sourced_timestamp_is_obtained():
    with temporary_images(["IMG_20100102_030405.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            enabled_preprocessors=[
                ("processor", {}),
            ],
        )

        importer.preprocessors[0].process.return_value = {
            FactType.TAKEN_TIMESTAMP: datetime(2010, 1, 2, 3, 4, 5)
        }

        importer.process_photos()

        dest_dir = target_root / "2010" / "2010-01"
        expected_path = dest_dir / image_paths[0].name
        date = ExifData.extract_date(expected_path)

        assert date is not None
        assert date.year == 2025
        assert expected_path.exists()
        assert not image_paths[0].exists()


@pytest.mark.parametrize("extension", ["jpg", "jpeg", "tif", "tiff", "arw"])
def test_process_photos_handles_files_with_supported_extensions(
    input_dir, target_root, extension
):
    importer = Importer(input_path=input_dir, target_root=target_root)

    file_path = input_dir / f"foo.{extension}"
    file_path.write_bytes(b"bar")

    with patch.object(
        ExifData, "extract_date", Mock(return_value=datetime(2020, 1, 1))
    ):
        importer.process_photos()

    assert not file_path.exists()
    assert (target_root / "2020" / "2020-01" / f"foo.{extension}").exists()


@pytest.mark.parametrize("extension", ["mp4", "txt", ""])
def test_process_photos_skips_unsupported_files(input_dir, target_root, extension):
    importer = Importer(input_path=input_dir, target_root=target_root)

    file_path = input_dir / f"foo.{extension}"
    file_path.write_text("bar")

    importer.process_photos()

    assert file_path.exists()
    skipped = [i for i in importer.report.get_report() if type(i) is SkippedReportItem]
    assert len(skipped) == 1
    assert str(file_path) in str(skipped[0])


def test_process_photos_moves_files(stub_user_dirs):
    user_data_path, _ = stub_user_dirs
    with temporary_images(["IMG_20240909_103402.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        dest_dir = target_root / "2024" / "2024-09"
        moved = dest_dir / image_paths[0].name

        assert moved.exists()
        assert not image_paths[0].exists()
        assert any(user_data_path.glob("reports/*.html"))


def test_process_photos_leaves_files_in_place_for_dry_runs(stub_user_dirs):
    user_data_path, _ = stub_user_dirs
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=True,
        )

        importer.process_photos()

        dest_dir = target_root / "2024" / "2024-09"
        moved = dest_dir / image_paths[0].name

        assert image_paths[0].exists()
        assert not moved.exists()
        assert any(user_data_path.glob("reports/*.html"))


@pytest.mark.parametrize("dry_run", [True, False])
def test_process_photos_logs_file_moves_to_report(dry_run):
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=dry_run,
        )
        importer.process_photos()

        moved_item = next(
            (
                item
                for item in importer.report.get_report()
                if type(item) is MoveReportItem
            )
        )

        assert moved_item
        assert "Canon_40D.jpg" in moved_item.destination


@patch("fotura.importer.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
def test_process_executes_postprocessors_for_files_that_can_be_handled():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_postprocessors=[("dummy_postprocessor", {})],
        )
        importer.process_photos()

        importer.postprocessors[0].process.assert_called()


@patch("fotura.importer.POSTPROCESSOR_MAP", {"dummy_postprocessor": DummyPostprocessor})
def test_process_skips_postprocessor_execution_for_files_that_cannot_be_handled():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_postprocessors=[("dummy_postprocessor", {})],
        )

        importer.postprocessors[0].can_handle.return_value = False
        importer.process_photos()

        importer.postprocessors[0].process.assert_not_called()


def test_process_photos_skips_when_a_timestamp_cannot_be_obtained():
    with temporary_images(["no-date.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )
        importer.process_photos()

        skipped_item = next(
            (
                item
                for item in importer.report.get_report()
                if type(item) is SkippedReportItem
            )
        )
        assert skipped_item
        assert "no-date.jpg" in skipped_item.__repr__()
        assert image_paths[0].exists()


@patch.object(shutil, "move", side_effect=ValueError)
def test_process_photos_logs_failed_on_move_exception(_):
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        importer.process_photos()

        failed_item = next(
            (
                item
                for item in importer.report.get_report()
                if type(item) is FailedReportItem
            )
        )
        assert failed_item
        assert "Canon_40D.jpg" in str(failed_item)
        assert image_paths[0].exists()


@patch.object(ExifData, "extract_date", side_effect=ValueError)
def test_process_photos_halts_on_exception(_):
    with temporary_images(["Canon_40D.jpg", "sony_alpha_a58.JPG"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        importer.process_photos()

        assert image_paths[0].exists()
        assert image_paths[1].exists()

        failed_items = list(
            item
            for item in importer.report.get_report()
            if type(item) is FailedReportItem
        )

        assert len(failed_items) == 1


def test_process_skips_destination_directory_creation_for_dry_runs():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        target_dir = target_root / "2008" / "2008-05"
        importer = Importer(
            input_path=input_path, target_root=target_root, dry_run=True
        )

        importer.process_photos()

        assert not target_dir.exists()


def test_filename_collision_increment_when_target_exists():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        target_dir = target_root / "2008" / "2008-05"
        os.makedirs(target_dir)
        shutil.copy(image_paths[0], target_dir)

        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        importer.process_photos()

        assert not image_paths[0].exists()
        assert (target_dir / "Canon_40D.jpg").exists()
        assert (target_dir / "Canon_40D_1.jpg").exists()


def test_filename_collision_keep_both_strategy_when_inputs_resolve_to_same_path():
    with temporary_images(
        [Path("directory") / "Pentax_K10D.jpg", Path("directory2") / "Pentax_K10D.jpg"]
    ) as (input_path, target_root, image_paths):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            conflict_resolution_strategy="keep_both",
        )

        importer.process_photos()

        assert not image_paths[0].exists()
        target_dir = target_root / "2008" / "2008-05"
        assert (target_dir / "Pentax_K10D.jpg").exists()
        assert (target_dir / "Pentax_K10D_1.jpg").exists()


def test_filename_collision_skip_strategy_when_inputs_resolve_to_same_path():
    with temporary_images(
        [Path("directory") / "Pentax_K10D.jpg", Path("directory2") / "Pentax_K10D.jpg"]
    ) as (input_path, target_root, image_paths):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            conflict_resolution_strategy="skip",
        )

        importer.process_photos()

        assert not image_paths[0].exists()
        assert image_paths[1].exists()

        target_dir = target_root / "2008" / "2008-05"
        assert (target_dir / "Pentax_K10D.jpg").exists()
        files_in_directory = list(helper.get_all_files(target_dir))
        assert len(files_in_directory) == 1


def test_filename_collisions_are_handled_when_logged_in_dry_run_mode():
    with temporary_images(
        [Path("directory") / "Pentax_K10D.jpg", Path("directory2") / "Pentax_K10D.jpg"]
    ) as (input_path, target_root, _):
        importer = Importer(
            input_path=input_path, target_root=target_root, dry_run=True
        )

        importer.process_photos()

        moved_items = list(
            item
            for item in importer.report.get_report()
            if type(item) is MoveReportItem
        )

        destinations = [item.destination for item in moved_items]
        assert len(destinations) == 2
        assert str(target_root / "2008" / "2008-05" / "Pentax_K10D.jpg") in destinations
        assert (
            str(target_root / "2008" / "2008-05" / "Pentax_K10D_1.jpg") in destinations
        )


def test_permission_check_raises_on_write_error(fs, tmp_path):
    if os.name == "nt":
        fs.create_dir(tmp_path, perm_bits=0o444)
    else:
        fs.create_dir(tmp_path, perm_bits=0o555)

    with pytest.raises(
        PermissionError, match="Permission check: Failed to write test file"
    ):
        Importer(input_path=tmp_path, target_root=tmp_path)


def test_permission_check_raises_on_remove_error(fs, tmp_path):
    temp_file = tmp_path / "permission-check.tmp"
    fs.create_file(temp_file)

    if os.name == "nt":
        os.chmod(temp_file, 0o444)
    else:
        os.chmod(tmp_path, 0o555)

    with pytest.raises(
        PermissionError, match="Permission check: Failed to remove test file"
    ):
        Importer(input_path=tmp_path, target_root=tmp_path)


def test_process_photos_makes_read_only_files_writable(stub_user_dirs):
    user_data_path, _ = stub_user_dirs
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        # Set file to read-only
        os.chmod(image_paths[0], stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        initial_mode = image_paths[0].stat().st_mode
        assert not (initial_mode & stat.S_IWRITE), "File should start as read-only"

        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
        )

        importer.process_photos()

        dest_dir = target_root / "2008" / "2008-05"
        moved = dest_dir / image_paths[0].name

        assert moved.exists()
        assert not image_paths[0].exists()
        assert any(user_data_path.glob("reports/*.html"))

        moved_mode = moved.stat().st_mode
        assert moved_mode & stat.S_IWRITE, (
            "Moved file should have write permissions (read-only flag should have been removed)"
        )


@patch("fotura.importer.PREPROCESSOR_MAP", {"dummy_preprocessor": DummyPreprocessor})
@patch(
    "fotura.importer.POSTPROCESSOR_MAP",
    {
        "dummy_postprocessor": DummyPostprocessor,
        "complex_dummy_postprocessor": ComplexDummyPostprocessor,
    },
)
def test_processor_facts_are_accumulated_through_processor_calls():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_preprocessors=[("dummy_preprocessor", {})],
            enabled_postprocessors=[
                ("dummy_postprocessor", {}),
                ("complex_dummy_postprocessor", {"max_size": 100}),
            ],
        )

        importer.preprocessors[0].process.return_value = {
            "preprocessor_fact": "preprocessor_value",
        }
        importer.postprocessors[0].process.return_value = {
            "postprocessor_fact": "postprocessor_value",
        }
        importer.postprocessors[1].process.return_value = {
            "complex_postprocessor_fact": "complex_postprocessor_value",
        }

        importer.process_photos()

        importer.preprocessors[0].process.assert_called_once()
        importer.postprocessors[0].process.assert_called_once()
        importer.postprocessors[1].process.assert_called_once()

        # Verify final state contains all three accumulated facts
        final_facts = importer.postprocessors[1].process.call_args[0][1]
        expected_facts = {
            "preprocessor_fact": "preprocessor_value",
            "postprocessor_fact": "postprocessor_value",
            "complex_postprocessor_fact": "complex_postprocessor_value",
        }
        assert final_facts == expected_facts
