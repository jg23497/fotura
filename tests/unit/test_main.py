from importlib import reload
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fotura import importer, main
from tests.helpers.helper import temporary_images
from tests.helpers.processors import (
    ComplexDummyPostprocessor,
    ComplexDummyPreprocessor,
    DummyPostprocessor,
    DummyPreprocessor,
)


def test_main_tidies_image_files():
    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        input_image_paths,
    ):
        result = CliRunner().invoke(
            main.main,
            [
                str(input_path),
                str(target_root),
                "--preprocessors",
                "filename_timestamp_extract",
            ],
        )
        new_image_path = target_root / "2008" / "2008-05" / input_image_paths[0].name

        assert not input_image_paths[0].exists()
        assert new_image_path.exists()
        assert result.exit_code == 0, result.output


@patch(
    "fotura.processors.registry.PREPROCESSOR_MAP",
    {
        "complex_preprocessor": ComplexDummyPreprocessor,
        "other_preprocessor": DummyPreprocessor,
    },
)
def test_help_lists_available_preprocessors():
    reload(main)

    result = CliRunner().invoke(
        main.main,
        ["--help"],
    )

    stdout = result.stdout.replace("  ", "")

    assert "- other_preprocessor: no parameters" in stdout
    assert (
        "- complex_preprocessor: max_size(int),\nshould_do_something(bool)\n\n"
        in stdout
    )


@patch(
    "fotura.processors.registry.PREPROCESSOR_MAP",
    {
        "other_preprocessor": DummyPreprocessor,
    },
)
def test_fails_when_unknown_preprocessor_specified():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.main,
            [
                str(input_path),
                str(target_root),
                "--preprocessors",
                "filename_timestamp_extract",
            ],
        )

        assert result.exit_code == 1


@patch(
    "fotura.processors.registry.PREPROCESSOR_MAP",
    {
        "complex_preprocessor": ComplexDummyPreprocessor,
    },
)
def test_passes_command_line_arguments_to_preprocessors():
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
                main.main,
                [
                    str(input_path),
                    str(target_root),
                    "--preprocessors",
                    "complex_preprocessor:max_size=1,should_do_something=true",
                ],
            )

            assert result.exit_code == 0

            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args

            assert kwargs["enabled_preprocessors"] == [
                ("complex_preprocessor", {"max_size": 1, "should_do_something": True})
            ]


@patch(
    "fotura.processors.registry.PREPROCESSOR_MAP",
    {
        "complex_preprocessor": ComplexDummyPreprocessor,
    },
)
def test_main_invalid_preprocessor_argument_type():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.main,
            [
                str(input_path),
                str(target_root),
                "--preprocessors",
                "complex_preprocessor:max_size=foo",
            ],
        )

        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)
        assert "Cannot cast 'foo' to <class 'int'>:" in str(result.exception)


@patch(
    "fotura.processors.registry.POSTPROCESSOR_MAP",
    {
        "complex_postprocessor": ComplexDummyPreprocessor,
        "other_postprocessor": DummyPostprocessor,
    },
)
def test_help_lists_available_postprocessors():
    reload(main)

    result = CliRunner().invoke(
        main.main,
        ["--help"],
    )

    stdout = result.stdout.replace("  ", "")

    assert "- other_postprocessor: no parameters" in stdout
    assert (
        "- complex_postprocessor: max_size(int),\nshould_do_something(bool)\n\n"
        in stdout
    )


@patch(
    "fotura.processors.registry.POSTPROCESSOR_MAP",
    {
        "other_postprocessor": DummyPostprocessor,
    },
)
def test_fails_when_unknown_postprocessor_specified():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.main,
            [
                str(input_path),
                str(target_root),
                "--postprocessors",
                "foo",
            ],
        )

        assert result.exit_code == 1


@patch(
    "fotura.processors.registry.POSTPROCESSOR_MAP",
    {
        "complex_postprocessor": ComplexDummyPostprocessor,
    },
)
def test_passes_command_line_arguments_to_postprocessors():
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
                main.main,
                [
                    str(input_path),
                    str(target_root),
                    "--postprocessors",
                    "complex_postprocessor:max_size=1,should_do_something=true",
                ],
            )

            assert result.exit_code == 0

            mock_init.assert_called_once()
            _, kwargs = mock_init.call_args

            assert kwargs["enabled_postprocessors"] == [
                ("complex_postprocessor", {"max_size": 1, "should_do_something": True})
            ]


@patch(
    "fotura.processors.registry.POSTPROCESSOR_MAP",
    {
        "complex_postprocessor": ComplexDummyPostprocessor,
    },
)
def test_main_invalid_postprocessor_argument_type():
    reload(main)

    with temporary_images(["Canon_40D.jpg"]) as (
        input_path,
        target_root,
        _,
    ):
        result = CliRunner().invoke(
            main.main,
            [
                str(input_path),
                str(target_root),
                "--postprocessors",
                "complex_postprocessor:max_size=foo",
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
            main.main,
            [str(input_path), str(target_root), "--target-path-format", format],
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
            main.main,
            [
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
