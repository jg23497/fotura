from pathlib import Path

import pytest

from fotura.importing.conflict_resolution.strategies.skip_strategy import SkipStrategy


@pytest.fixture
def target_path(fs, target_root) -> Path:
    path = target_root / "foo" / "bar.jpg"
    fs.create_dir(target_root / "foo")
    fs.create_file(str(path))
    return path


@pytest.fixture
def strategy() -> SkipStrategy:
    return SkipStrategy()


def test_returns_no_target_path(strategy, target_path):
    claimed_paths = set()

    result = strategy.resolve(target_path=target_path, claimed_paths=claimed_paths)

    assert result is None
