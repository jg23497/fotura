import logging
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from fotura.domain.photo import Photo
from fotura.importer import Importer
from fotura.io.photos.exif_data import ExifData
from fotura.processors.fact_type import FactType
from tests.helpers import helper
from tests.helpers.helper import (
    get_log_entries,
    temporary_images,
)
from tests.helpers.processors import (
    ComplexDummyAfterEachProcessor,
    DummyAfterEachProcessor,
    DummyBeforeEachProcessor,
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


@patch(
    "fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP",
    {"dummy_before_each_processor": DummyBeforeEachProcessor},
)
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_before_each_processors(input_dir, target_root, dry_run):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_before_each_processors=[("dummy_before_each_processor", {})],
    )

    assert len(importer.processor_orchestrator.before_each_processors) == 1
    assert isinstance(
        importer.processor_orchestrator.before_each_processors[0],
        DummyBeforeEachProcessor,
    )
    assert (
        importer.processor_orchestrator.before_each_processors[0].context.dry_run
        is dry_run
    )


@patch(
    "fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP",
    {"dummy_after_each_processor": DummyAfterEachProcessor},
)
@pytest.mark.parametrize("dry_run", [True, False])
def test_initializes_after_each_processors(input_dir, target_root, dry_run):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        dry_run=dry_run,
        enabled_after_each_processors=[("dummy_after_each_processor", {})],
    )

    assert len(importer.processor_orchestrator.after_each_processors) == 1
    assert isinstance(
        importer.processor_orchestrator.after_each_processors[0],
        DummyAfterEachProcessor,
    )
    assert (
        importer.processor_orchestrator.after_each_processors[0].context.dry_run
        is dry_run
    )


@patch(
    "fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP",
    {"dummy_after_each_processor": DummyAfterEachProcessor},
)
def test_calls_configure_on_after_each_processors(input_dir, target_root):
    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        enabled_before_each_processors=[],
        enabled_after_each_processors=[("dummy_after_each_processor", {})],
    )

    assert importer.processor_orchestrator.after_each_processors[0].configure.called


@patch("fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP", {})
@patch("fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP", {})
def test_exits_when_unknown_before_each_processor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Importer(
            input_path=input_dir,
            target_root=target_root,
            enabled_before_each_processors=[("foobar", {})],
        )


@patch("fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP", {})
@patch("fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP", {})
def test_exits_when_unknown_after_each_processor_is_specified(input_dir, target_root):
    with pytest.raises(SystemExit):
        Importer(
            input_path=input_dir,
            target_root=target_root,
            enabled_after_each_processors=[("foobar", {})],
        )


## process_photos


@patch(
    "fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP",
    {"foo": DummyBeforeEachProcessor, "bar": DummyBeforeEachProcessor},
)
def test_last_before_each_processor_fact_takes_precedence(input_dir, target_root):
    image_path = input_dir / "img.jpg"
    image_path.write_bytes(b"foo")

    importer = Importer(
        input_path=input_dir,
        target_root=target_root,
        enabled_before_each_processors=[
            ("foo", {}),
            ("bar", {}),
        ],
    )

    importer.processor_orchestrator.before_each_processors[0].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2021, 1, 2, 3, 4, 5)
    }
    importer.processor_orchestrator.before_each_processors[1].process.return_value = {
        FactType.TAKEN_TIMESTAMP: datetime(2020, 1, 2, 3, 4, 5)
    }

    importer.process_photos()

    dest_dir = target_root / "2020" / "2020-01"
    expected_path = dest_dir / image_path.name
    assert expected_path.exists()
    assert not image_path.exists()


@patch(
    "fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP",
    {"processor": DummyBeforeEachProcessor},
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
            enabled_before_each_processors=[
                ("processor", {}),
            ],
        )

        importer.processor_orchestrator.before_each_processors[
            0
        ].process.return_value = {
            FactType.TAKEN_TIMESTAMP: datetime(2010, 1, 2, 3, 4, 5)
        }

        importer.process_photos()

        dest_dir = target_root / "2010" / "2010-01"
        expected_path = dest_dir / image_paths[0].name
        date = ExifData.extract_date(Photo(expected_path))

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
def test_process_photos_ignores_unsupported_files(
    input_dir, target_root, extension, caplog
):
    importer = Importer(input_path=input_dir, target_root=target_root)

    file_path = input_dir / f"foo.{extension}"
    file_path.write_text("bar")

    with caplog.at_level(logging.INFO):
        importer.process_photos()

    log_entries = get_log_entries(
        caplog,
        lambda r: r.levelno == logging.WARNING and r.getMessage().startswith("Ignored"),
    )

    assert file_path.exists()

    assert len(log_entries) == 1
    assert str(file_path) in log_entries[0].getMessage()


def test_process_photos_moves_files():
    with temporary_images(["IMG_20240909_103402.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        dest_dir = target_root / "2024" / "2024-09"
        moved = dest_dir / image_paths[0].name

        assert moved.exists()
        assert not image_paths[0].exists()


def test_process_photos_increments_moved_tally_when_photo_moved():
    with temporary_images(["IMG_20240909_103402.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        tally_snapshot = importer.tally.get_snapshot()
        assert tally_snapshot.get("moved") == 1


def test_process_photos_leaves_files_in_place_for_dry_runs():
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


@pytest.mark.parametrize("dry_run", [True, False])
def test_process_photos_logs_file_moves_to_report(dry_run, caplog):
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

        with caplog.at_level(logging.INFO):
            importer.process_photos()

        log_entries = get_log_entries(
            caplog,
            lambda r: r.levelno == logging.INFO and r.getMessage().startswith("Moved"),
        )

        assert len(log_entries) == 1

        assert "Canon_40D.jpg" in str(log_entries[0].media_file)
        assert str("Canon_40D.jpg") in log_entries[0].getMessage()


@patch(
    "fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP",
    {"dummy_after_each_processor": DummyAfterEachProcessor},
)
def test_process_executes_after_each_processors_for_files_that_can_be_handled():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_after_each_processors=[("dummy_after_each_processor", {})],
        )
        importer.process_photos()

        importer.processor_orchestrator.after_each_processors[0].process.assert_called()


@patch(
    "fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP",
    {"dummy_after_each_processor": DummyAfterEachProcessor},
)
def test_process_skips_after_each_processor_execution_for_files_that_cannot_be_handled():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=False,
            enabled_after_each_processors=[("dummy_after_each_processor", {})],
        )

        importer.processor_orchestrator.after_each_processors[
            0
        ].can_handle.return_value = False
        importer.process_photos()

        importer.processor_orchestrator.after_each_processors[
            0
        ].process.assert_not_called()


def test_process_photos_skips_when_a_timestamp_cannot_be_obtained(caplog):
    with temporary_images(["no-date.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        with caplog.at_level(logging.INFO):
            importer.process_photos()

        log_entries = get_log_entries(
            caplog,
            lambda r: r.levelno == logging.WARNING
            and r.getMessage().startswith("Skipping file: no date found"),
        )

        assert len(log_entries) == 1
        assert "no-date.jpg" in str(log_entries[0].media_file)


def test_process_photos_increments_skipped_tally_when_photo_skipped():
    with temporary_images(["no-date.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        tally_snapshot = importer.tally.get_snapshot()
        assert tally_snapshot.get("skipped") == 1


@patch.object(shutil, "move", side_effect=ValueError)
def test_process_photos_logs_failed_on_move_exception(_, caplog):
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        with caplog.at_level(logging.INFO):
            importer.process_photos()

        log_entries = get_log_entries(
            caplog,
            lambda r: r.levelno == logging.ERROR
            and "Failed to import" in r.getMessage()
            and r.exc_info[0] is ValueError,
        )

        assert len(log_entries) == 1
        assert "Canon_40D.jpg" in str(log_entries[0].media_file)


@patch.object(ExifData, "extract_date", side_effect=ValueError)
def test_process_photos_halts_on_exception(_, caplog):
    with temporary_images(["Canon_40D.jpg", "sony_alpha_a58.JPG"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        with caplog.at_level(logging.INFO):
            importer.process_photos()

        assert image_paths[0].exists()
        assert image_paths[1].exists()

        log_entries = get_log_entries(
            caplog,
            lambda r: r.levelno == logging.ERROR
            and "Failed to import" in r.getMessage()
            and r.exc_info[0] is ValueError,
        )

        assert len(log_entries) == 1


@patch.object(ExifData, "extract_date", side_effect=ValueError)
def test_process_photos_increments_errored_tally_when_error_occurs(_):
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        importer.process_photos()

        tally_snapshot = importer.tally.get_snapshot()
        assert tally_snapshot.get("errored") == 1


def test_process_skips_destination_directory_creation_for_dry_runs():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        target_directory = target_root / "2008" / "2008-05"
        importer = Importer(
            input_path=input_path, target_root=target_root, dry_run=True
        )

        importer.process_photos()

        assert not target_directory.exists()


def test_filename_collision_increment_when_target_exists():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        image_paths,
    ):
        target_directory = target_root / "2008" / "2008-05"
        os.makedirs(target_directory)
        shutil.copy(image_paths[0], target_directory)

        importer = Importer(
            input_path=input_path,
            target_root=target_root,
        )

        importer.process_photos()

        assert not image_paths[0].exists()
        assert (target_directory / "Canon_40D.jpg").exists()
        assert (target_directory / "Canon_40D_1.jpg").exists()


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
        target_directory = target_root / "2008" / "2008-05"
        assert (target_directory / "Pentax_K10D.jpg").exists()
        assert (target_directory / "Pentax_K10D_1.jpg").exists()


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

        target_directory = target_root / "2008" / "2008-05"
        assert (target_directory / "Pentax_K10D.jpg").exists()
        files_in_directory = list(helper.get_all_files(target_directory))
        assert len(files_in_directory) == 1


def test_filename_collisions_are_handled_when_logged_in_dry_run_mode(caplog):
    with temporary_images(
        [
            Path("directory") / "Pentax_K10D.jpg",
            Path("directory2") / "Pentax_K10D.jpg",
        ]
    ) as (input_path, target_root, _):
        importer = Importer(
            input_path=input_path,
            target_root=target_root,
            dry_run=True,
        )

        with caplog.at_level(logging.INFO):
            importer.process_photos()

    log_entries = get_log_entries(
        caplog,
        lambda r: (r.levelno == logging.INFO and r.getMessage().startswith("Moved")),
    )

    destinations = [r.getMessage() for r in log_entries]
    assert len(log_entries) == 2

    assert any(
        str(target_root / "2008" / "2008-05" / "Pentax_K10D.jpg") in msg
        for msg in destinations
    )

    assert any(
        str(target_root / "2008" / "2008-05" / "Pentax_K10D_1.jpg") in msg
        for msg in destinations
    )


def test_permission_check_raises_on_write_error(fs):
    path = Path("/data/testdir")

    if os.name == "nt":
        fs.create_dir(path, perm_bits=0o444)
    else:
        fs.create_dir(path, perm_bits=0o555)

    with pytest.raises(
        PermissionError, match="Permission check: Failed to write test file"
    ):
        importer = Importer(input_path=path, target_root=path)
        importer.process_photos()


def test_permission_check_raises_on_remove_error(fs):
    path = Path("/data/testdir")
    temp_file = path / "permission-check.tmp"
    fs.create_file(temp_file)

    if os.name == "nt":
        os.chmod(path, 0o444)
    else:
        os.chmod(path, 0o555)

    with pytest.raises(
        PermissionError, match="Permission check: Failed to remove test file"
    ):
        importer = Importer(input_path=path, target_root=path)
        importer.process_photos()


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

        moved_mode = moved.stat().st_mode
        assert moved_mode & stat.S_IWRITE, (
            "Moved file should have write permissions (read-only flag should have been removed)"
        )


@patch(
    "fotura.processors.processor_orchestrator.BEFORE_EACH_PROCESSOR_MAP",
    {"dummy_before_each_processor": DummyBeforeEachProcessor},
)
@patch(
    "fotura.processors.processor_orchestrator.AFTER_EACH_PROCESSOR_MAP",
    {
        "dummy_after_each_processor": DummyAfterEachProcessor,
        "complex_dummy_after_each_processor": ComplexDummyAfterEachProcessor,
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
            enabled_before_each_processors=[("dummy_before_each_processor", {})],
            enabled_after_each_processors=[
                ("dummy_after_each_processor", {}),
                ("complex_dummy_after_each_processor", {"max_size": 100}),
            ],
        )

        importer.processor_orchestrator.before_each_processors[
            0
        ].process.return_value = {
            "before_each_processor_fact": "before_each_processor_value",
        }
        importer.processor_orchestrator.after_each_processors[
            0
        ].process.return_value = {
            "after_each_processor_fact": "after_each_processor_value",
        }
        importer.processor_orchestrator.after_each_processors[
            1
        ].process.return_value = {
            "complex_after_each_processor_fact": "complex_after_each_processor_value",
        }

        importer.process_photos()

        importer.processor_orchestrator.before_each_processors[
            0
        ].process.assert_called_once()
        importer.processor_orchestrator.after_each_processors[
            0
        ].process.assert_called_once()
        importer.processor_orchestrator.after_each_processors[
            1
        ].process.assert_called_once()

        # Verify final state contains all three accumulated facts
        photo = importer.processor_orchestrator.after_each_processors[
            1
        ].process.call_args[0][0]

        expected_facts = {
            "before_each_processor_fact": "before_each_processor_value",
            "after_each_processor_fact": "after_each_processor_value",
            "complex_after_each_processor_fact": "complex_after_each_processor_value",
        }
        assert photo.facts == expected_facts
