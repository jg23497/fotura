from typing import Optional
import pytest
from pathlib import Path
from bs4 import BeautifulSoup, Tag

from photo_tidy.tidy import Tidy
from tests.helpers.helper import all_temporary_images


def clean_text(element: Optional[Tag]) -> str:
    if element is None:
        return ""
    return element.get_text(separator=" ", strip=True)


@pytest.fixture
def report(stub_user_dirs):
    user_data_path, _ = stub_user_dirs

    with all_temporary_images() as (input_path, target_root):
        tidy = Tidy(
            Path(input_path),
            Path(target_root),
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )
        tidy.process_photos()

        report_files = list((user_data_path / "reports").glob("*.html"))
        assert report_files, "Expect a report to have been generated."

        latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
        soup = BeautifulSoup(latest_report.read_text(encoding="utf-8"), "html.parser")

        return soup


def test_report_summary_information(report):
    title = report.find("title")
    assert title is not None, "Report should have a <title> element."
    assert "Photo Tidy" in title.text, f"Unexpected title: {title.text}"

    moved_card_text = clean_text(report.select_one(".card.main"))
    assert "Total 11" in moved_card_text

    moved_card_text = clean_text(report.select_one(".card.moved"))
    assert "Moved 9" in moved_card_text

    moved_card_text = clean_text(report.select_one(".card.ignored"))
    assert "Skipped 2" in moved_card_text


def test_report_table_rows(report):
    expected = [
        ["test.txt", "Skipped", "Reason: .txt not in supported file extensions"],
        ["IMG-20250521-WA0002.jpg", "Moved", "Destination"],
        ["no-date.jpg", "Skipped", "Reason: No date found"],
        ["sony_alpha_a58.JPG", "Moved", "Destination"],
        ["date-time-digitized-only.jpg", "Moved", "Destination"],
        ["date-time-only.jpg", "Moved", "Destination"],
        ["IMG_20100102_030405.jpg", "Moved", "Destination"],
        ["IMG_20240909_103402.jpg", "Moved", "Destination"],
        ["Canon_40D.jpg", "Moved", "Destination"],
        ["Pentax_K10D.jpg", "Moved", "Destination"],
        ["Pentax_K10D.jpg", "Moved", "Pentax_K10D_1.jpg"],
    ]

    rows = report.select("table tr")
    assert len(rows) > 1, "Expected more than one table row in the report."

    headers = [clean_text(i) for i in rows[0].select("th")]
    assert headers == ["File", "Category", "Description"]

    for row_index, tr in enumerate(rows[1:], start=0):
        cells = [clean_text(td) for td in tr.select("td")]
        assert len(cells) == 3, f"Row {row_index} should have 3 columns."

        if row_index >= len(expected):
            pytest.fail(f"No expected values provided for row {row_index}: {cells}")  # type: ignore

        for cell_index, cell in enumerate(cells):
            expected_value = expected[row_index][cell_index]
            assert expected_value in cell, (
                f"Mismatch at row {row_index}, col {cell_index}: "
                f"expected '{expected_value}' in '{cell}'"
            )
