from unittest.mock import patch

from click.testing import CliRunner

from fotura.cli.processor_commands import (
    build_resume_subcommand,
    build_run_subcommand,
)
from tests.helpers.processors import (
    ComplexDummyAfterAllProcessor,
    DummyAfterAllProcessor,
    ResumableDummyAfterAllProcessor,
)

# build_run_subcommand


def test_run_subcommand_processes_empty_source_directory(tmp_path):
    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": DummyAfterAllProcessor},
    ):
        cmd = build_run_subcommand("dummy", DummyAfterAllProcessor, tmp_path)
        result = CliRunner().invoke(cmd, [str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Processed 0 file(s)." in result.output


def test_run_subcommand_echoes_processed_count(tmp_path):
    for i in range(3):
        (tmp_path / f"photo{i}.jpg").write_bytes(b"x")

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": DummyAfterAllProcessor},
    ):
        cmd = build_run_subcommand("dummy", DummyAfterAllProcessor, tmp_path)
        result = CliRunner().invoke(cmd, [str(tmp_path)])

    assert "Processed 3 file(s)." in result.output


def test_run_subcommand_passes_processor_args(tmp_path):
    instances = []

    class CapturingProcessor(ComplexDummyAfterAllProcessor):
        def __init__(self, context, concurrency=2):
            super().__init__(context, concurrency=concurrency)
            instances.append(self)

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": CapturingProcessor},
    ):
        cmd = build_run_subcommand("dummy", ComplexDummyAfterAllProcessor, tmp_path)
        result = CliRunner().invoke(cmd, [str(tmp_path), "--concurrency", "5"])

    assert result.exit_code == 0, result.output
    assert len(instances) == 1
    assert instances[0].concurrency == 5


# build_resume_subcommand


def test_resume_subcommand_calls_resume(tmp_path):
    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": ResumableDummyAfterAllProcessor},
    ):
        cmd = build_resume_subcommand(
            "dummy", ResumableDummyAfterAllProcessor, tmp_path
        )
        result = CliRunner().invoke(cmd, [])

    assert result.exit_code == 0, result.output

