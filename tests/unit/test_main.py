import re
from importlib import reload
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from fotura import importer, main
from tests.helpers.helper import temporary_images
from tests.helpers.processors import (
    ComplexDummyAfterEachProcessor,
    ComplexDummyBeforeEachProcessor,
    DummyAfterAllProcessor,
    DummyAfterEachProcessor,
    DummyBeforeEachProcessor,
)


def test_main_tidies_image_files():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        input_image_paths,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--before-each",
                "filename_timestamp_extract",
            ],
        )
        new_image_path = target_root / "2008" / "2008-05" / input_image_paths[0].name

        assert not input_image_paths[0].exists()
        assert new_image_path.exists()
        assert result.exit_code == 0, result.output


@patch(
    "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
    {
        "complex_before_each_processor": ComplexDummyBeforeEachProcessor,
        "other_before_each_processor": DummyBeforeEachProcessor,
    },
)
def test_help_lists_available_before_each_processors():
    reload(main)

    result = CliRunner().invoke(
        main.cli,
        ["import", "--help"],
    )

    stdout = normalize_whitespace(result.stdout)

    assert "- other_before_each_processor: no parameters" in stdout
    assert (
        "- complex_before_each_processor: max_size(int), should_do_something(bool)"
        in stdout
    )


@patch(
    "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
    {
        "other_before_each_processor": DummyBeforeEachProcessor,
    },
)
def test_fails_when_unknown_before_each_processor_specified():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--before-each",
                "filename_timestamp_extract",
            ],
        )

        assert result.exit_code == 2
        assert "Unknown processor 'filename_timestamp_extract'" in result.output
        assert "Valid options:" in result.output


@patch(
    "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
    {
        "complex_before_each_processor": ComplexDummyBeforeEachProcessor,
    },
)
def test_passes_command_line_arguments_to_before_each_processors():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        with (
            patch.object(importer.Importer, "__init__", return_value=None) as mock_init,
            patch.object(importer.Importer, "process_photos", return_value=None),
        ):
            result = CliRunner().invoke(
                main.cli,
                [
                    "import",
                    str(input_path),
                    str(target_root),
                    "--before-each",
                    "complex_before_each_processor:max_size=1,should_do_something=true",
                ],
            )

            assert result.exit_code == 0

            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args

            assert kwargs["enabled_before_each_processors"] == [
                (
                    "complex_before_each_processor",
                    {"max_size": 1, "should_do_something": True},
                )
            ]


@patch(
    "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
    {
        "complex_before_each_processor": ComplexDummyBeforeEachProcessor,
    },
)
def test_main_invalid_before_each_processor_argument_type():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--before-each",
                "complex_before_each_processor:max_size=foo",
            ],
        )

        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)
        assert "Cannot cast 'foo' to <class 'int'>:" in str(result.exception)


@patch(
    "fotura.processors.registry.AFTER_EACH_PROCESSOR_MAP",
    {
        "complex_after_each_processor": ComplexDummyBeforeEachProcessor,
        "other_after_each_processor": DummyAfterEachProcessor,
    },
)
def test_help_lists_available_after_each_processors():
    reload(main)

    result = CliRunner().invoke(
        main.cli,
        ["import", "--help"],
    )

    stdout = normalize_whitespace(result.stdout)

    assert "- other_after_each_processor: no parameters" in stdout
    assert (
        "- complex_after_each_processor: max_size(int), should_do_something(bool)"
        in stdout
    )


@patch(
    "fotura.processors.registry.AFTER_EACH_PROCESSOR_MAP",
    {
        "other_after_each_processor": DummyAfterEachProcessor,
    },
)
def test_fails_when_unknown_after_each_processor_specified():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--after-each",
                "foo",
            ],
        )

        assert result.exit_code == 2
        assert "Unknown processor 'foo'" in result.output
        assert "Valid options:" in result.output


@patch(
    "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
    {
        "other_after_all_processor": DummyAfterAllProcessor,
    },
)
def test_fails_when_unknown_after_all_processor_specified():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--after-all",
                "foo",
            ],
        )

        assert result.exit_code == 2
        assert "Unknown processor 'foo'" in result.output
        assert "Valid options:" in result.output


@patch(
    "fotura.processors.registry.AFTER_EACH_PROCESSOR_MAP",
    {
        "complex_after_each_processor": ComplexDummyAfterEachProcessor,
    },
)
def test_passes_command_line_arguments_to_after_each_processors():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        with (
            patch.object(importer.Importer, "__init__", return_value=None) as mock_init,
            patch.object(importer.Importer, "process_photos", return_value=None),
        ):
            result = CliRunner().invoke(
                main.cli,
                [
                    "import",
                    str(input_path),
                    str(target_root),
                    "--after-each",
                    "complex_after_each_processor:max_size=1,should_do_something=true",
                ],
            )

            assert result.exit_code == 0

            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args

            assert kwargs["enabled_after_each_processors"] == [
                (
                    "complex_after_each_processor",
                    {"max_size": 1, "should_do_something": True},
                )
            ]


@patch(
    "fotura.processors.registry.AFTER_EACH_PROCESSOR_MAP",
    {
        "complex_after_each_processor": ComplexDummyAfterEachProcessor,
    },
)
def test_main_invalid_after_each_processor_argument_type():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--after-each",
                "complex_after_each_processor:max_size=foo",
            ],
        )

        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)
        assert "Cannot cast 'foo' to <class 'int'>:" in str(result.exception)


@pytest.mark.parametrize("format", ["foo/%g", "%Q-%m-%d"])
def test_fails_when_invalid_path_format_is_provided(format):
    with temporary_images([]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--target-path-format",
                format,
            ],
        )

        assert result.exit_code == 2, result.output
        assert isinstance(result.exception, SystemExit)
        assert "Target path format is invalid" in str(result.stderr)


def test_uses_custom_path_format_when_provided():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        input_image_paths,
    ):
        result = CliRunner().invoke(
            main.cli,
            [
                "import",
                str(input_path),
                str(target_root),
                "--target-path-format",
                "%Y/%m/%Y-%m-%d",
            ],
        )

        new_image_path = (
            target_root / "2008" / "05" / "2008-05-30" / input_image_paths[0].name
        )

        assert not input_image_paths[0].exists()
        assert new_image_path.exists()
        assert result.exit_code == 0, result.output


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# processor run


def test_processor_run_calls_orchestrator_with_source(tmp_path):
    with patch(
        "fotura.cli.processor_commands.ProcessorOrchestrator"
    ) as mock_orchestrator_class:
        mock_orchestrator = Mock()
        mock_orchestrator.run_on_source.return_value = 1
        mock_orchestrator_class.return_value = mock_orchestrator

        result = CliRunner().invoke(
            main.cli,
            ["processor", "run", "filename_timestamp_extract", str(tmp_path)],
        )

    assert result.exit_code == 0, result.output
    mock_orchestrator.run_on_source.assert_called_once_with(tmp_path)


def test_processor_run_prints_processed_count(tmp_path):
    with patch(
        "fotura.cli.processor_commands.ProcessorOrchestrator"
    ) as mock_orchestrator_class:
        mock_orchestrator = Mock()
        mock_orchestrator.run_on_source.return_value = 42
        mock_orchestrator_class.return_value = mock_orchestrator

        result = CliRunner().invoke(
            main.cli,
            ["processor", "run", "filename_timestamp_extract", str(tmp_path)],
        )

    assert "Processed 42 file(s)." in result.output


# processor resume


def test_processor_resume_delegates_to_orchestrator(tmp_path):
    with patch(
        "fotura.cli.processor_commands.ProcessorOrchestrator"
    ) as mock_orchestrator_class:
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        result = CliRunner().invoke(
            main.cli,
            ["processor", "resume", "google_photos_upload_batch"],
        )

    assert result.exit_code == 0, result.output
    mock_orchestrator.resume.assert_called_once()


def test_processor_resume_raises_usage_error_when_orchestrator_raises(tmp_path):
    with patch(
        "fotura.cli.processor_commands.ProcessorOrchestrator"
    ) as mock_orchestrator_class:
        mock_orchestrator = Mock()
        mock_orchestrator.resume.side_effect = ValueError(
            "Processor does not support resuming"
        )
        mock_orchestrator_class.return_value = mock_orchestrator

        result = CliRunner().invoke(
            main.cli,
            ["processor", "resume", "google_photos_upload_batch"],
        )

    assert result.exit_code == 2
    assert "does not support resuming" in result.output
