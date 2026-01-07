from datetime import datetime
from pathlib import Path

import pytest

from fotura.domain.photo import Photo
from fotura.importing.conflict_resolution.strategies.keep_both_strategy import (
    KeepBothStrategy,
)
from fotura.importing.conflict_resolution.strategies.skip_strategy import SkipStrategy
from fotura.io.path_resolver import PathResolver
from fotura.processors.fact_type import FactType
from fotura.reporting import Report, SkippedReportItem

# Fixtures


@pytest.fixture
def target_root(fs) -> Path:
    root = Path("~/Pictures")
    fs.create_dir(root)
    return root


@pytest.fixture
def report():
    return Report()


@pytest.fixture
def path_format():
    return "%Y/%m/%d"


@pytest.fixture
def resolver(request, target_root, path_format, report):
    dry_run = request.param
    return PathResolver(
        target_root=target_root,
        target_path_format=path_format,
        conflict_resolver=KeepBothStrategy(),
        report=report,
        dry_run=dry_run,
    )


@pytest.fixture
def photo(fs) -> Photo:
    path = Path("~/Desktop/test_image.jpg")
    fs.create_dir(path.parent)
    fs.create_file(path, contents=b"image")
    return Photo(path)


@pytest.fixture
def taken_date():
    return datetime(2024, 12, 31, 10, 30, 0)


# get_target_path


@pytest.mark.parametrize("resolver", [True, False], indirect=True)
def test_get_target_path_builds_path_from_taken_timestamp_fact(
    resolver, photo, taken_date
):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    target = resolver.get_target_path(photo)

    assert target == Path("~/Pictures/2024/12/31/test_image.jpg")


@pytest.mark.parametrize("resolver", [True, False], indirect=True)
def test_get_target_path_returns_none_and_logs_when_no_date_found(
    resolver, photo, report
):
    result = resolver.get_target_path(photo)

    assert result is None

    skipped = [item for item in report.get_report() if type(item) is SkippedReportItem]
    assert len(skipped) == 1
    assert skipped[0].reason == "No date found"


@pytest.mark.parametrize("resolver", [False], indirect=True)
def test_target_directory_is_created_when_not_dry_run(resolver, photo, taken_date):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    resolver.get_target_path(photo)

    assert Path("~/Pictures/2024/12/31").exists()


@pytest.mark.parametrize("resolver", [True], indirect=True)
def test_target_directory_is_not_created_when_dry_run(resolver, photo, taken_date):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    resolver.get_target_path(photo)

    assert not Path("~/Pictures/2024/12/31").exists()


@pytest.mark.parametrize("resolver", [False], indirect=True)
def test_existing_file_triggers_conflict_resolution(resolver, photo, taken_date, fs):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    target_directory = Path("~/Pictures/2024/12/31")
    fs.create_dir(target_directory)
    fs.create_file(target_directory / "test_image.jpg")

    target = resolver.get_target_path(photo)

    assert target == target_directory / "test_image_1.jpg"


@pytest.mark.parametrize("resolver", [False], indirect=True)
def test_claimed_path_triggers_conflict_resolution(resolver, photo, taken_date):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    original = Path("~/Pictures/2024/12/31/test_image.jpg")
    resolver.claimed_paths.add(original)

    target = resolver.get_target_path(photo)

    assert target == Path("~/Pictures/2024/12/31/test_image_1.jpg")


def test_skipped_conflict_resolution_writes_skipped_log_entry(
    target_root, path_format, report, photo, taken_date
):
    photo.facts[FactType.TAKEN_TIMESTAMP] = taken_date

    resolver = PathResolver(
        target_root=target_root,
        target_path_format=path_format,
        conflict_resolver=SkipStrategy(),
        report=report,
        dry_run=False,
    )

    target_directory = Path("~/Pictures/2024/12/31")
    target_directory.mkdir(parents=True)
    (target_directory / "test_image.jpg").touch()

    result = resolver.get_target_path(photo)

    assert result is None

    skipped = [item for item in report.get_report() if type(item) is SkippedReportItem]
    assert len(skipped) == 1
    assert skipped[0].reason == "Conflict resolution strategy"
