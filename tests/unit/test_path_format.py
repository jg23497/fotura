from datetime import datetime
from pathlib import Path
import pytest

from photo_tidy.path_format import PathFormat

# is_valid


@pytest.mark.parametrize(
    "format", ["foo/%%", "%Y/%Y-%m", "%Y/%m/%Y-%m-%d", "%Y%m%d", "%Y/%B %d", "a/b%%%%"]
)
def test_is_valid_returns_true_when_path_format_string_is_valid(format):
    assert PathFormat.is_valid(format)


@pytest.mark.parametrize(
    "format",
    ["foo/%g", "%Q-%m-%d", "a/b/%", "%YYYY/%MM/%DD", "%Y/%-m", "%F %T", "a/b%%%"],
)
def test_is_valid_returns_false_when_path_format_string_is_invalid(format):
    assert not PathFormat.is_valid(format)


# build_path


def test_build_path_returns_formatted_target_path():
    path = PathFormat.build_path(Path("/foo/bar"), datetime(1980, 1, 25), "%Y/%m/%d")

    assert path == Path("/foo/bar/1980/01/25")
