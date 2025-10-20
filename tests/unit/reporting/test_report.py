from pathlib import Path
from typing import Optional

import pytest
from bs4 import BeautifulSoup, Tag

from photo_tidy.reporting.failed_report_item import FailedReportItem
from photo_tidy.reporting.move_report_item import MoveReportItem
from photo_tidy.reporting.report import Report


def clean_text(element: Optional[Tag]) -> str:
    if element is None:
        return ""
    return element.get_text(separator=" ", strip=True)


@pytest.fixture
def report(stub_user_dirs) -> Report:
    return Report()


def test_report_logs_report_items(report):
    move_item = MoveReportItem(Path("file1.jpg"), Path("/dest/path1"))
    failed_item = FailedReportItem(
        Path("file2.txt"), Path("/dest/path2"), ValueError("oops")
    )

    report.log(move_item)
    report.log(failed_item)

    items = report.get_report()
    assert len(items) == 2
    assert items[0] == move_item
    assert items[1] == failed_item


def test_create_report_writes_html_file(report, stub_user_dirs):
    user_data_path, _ = stub_user_dirs

    report.log(MoveReportItem(Path("file1.jpg"), Path("/dest/path1")))
    report.log(
        FailedReportItem(Path("file2.txt"), Path("/dest/path2"), ValueError("Error"))
    )

    output_path = user_data_path / "reports" / "report.html"
    report.create_report(output_path)

    assert output_path.exists()
    assert report.report_path == output_path

    html = output_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("title") is not None


def test_summary_counts_in_html(report, stub_user_dirs):
    user_data_path, _ = stub_user_dirs

    report.log(MoveReportItem(Path("file1.jpg"), Path("/dest/path1")))
    report.log(MoveReportItem(Path("file2.jpg"), Path("/dest/path2")))
    report.log(
        FailedReportItem(Path("file3.txt"), Path("/dest/path3"), ValueError("Error"))
    )

    output_path = user_data_path / "reports" / "report.html"
    report.create_report(output_path)

    html = output_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    moved_card_text = clean_text(soup.select_one(".card.main"))
    assert "Total 3" in moved_card_text

    moved_card_text = clean_text(soup.select_one(".card.moved"))
    assert "Moved 2" in moved_card_text

    moved_card_text = clean_text(soup.select_one(".card.ignored"))
    assert "Skipped 0" in moved_card_text

    failed_card_text = clean_text(soup.select_one(".card.failed"))
    assert "Failed 1" in failed_card_text
