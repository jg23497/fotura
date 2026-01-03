import pytest

from fotura.importing.conflict_resolution.keep_both_strategy import KeepBothStrategy


@pytest.fixture
def strategy() -> KeepBothStrategy:
    return KeepBothStrategy()


def test_result_path_is_unchanged_if_no_conflict_found(strategy, target_root):
    target_path = target_root / "foo" / "bar.jpg"
    claimed_paths = set()

    result = strategy.resolve(target_path=target_path, claimed_paths=claimed_paths)

    assert result == target_path


def test_result_path_uses_incremented_filename_if_path_is_taken(
    fs, strategy, target_root
):
    target_path = target_root / "foo" / "bar.jpg"
    fs.create_dir(target_root / "foo")
    fs.create_file(str(target_root / "foo" / "bar.jpg"))
    claimed_paths = {target_root / "foo" / "bar_1.jpg"}

    result = strategy.resolve(target_path=target_path, claimed_paths=claimed_paths)

    assert result == target_root / "foo" / "bar_2.jpg"
