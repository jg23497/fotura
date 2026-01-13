from pathlib import Path
from typing import Optional

import pytest
from bs4 import BeautifulSoup, Tag

from fotura.importer import Importer
from tests.helpers.helper import all_temporary_images


def clean_text(element: Optional[Tag]) -> str:
    if element is None:
        return ""
    return element.get_text(separator=" ", strip=True)


@pytest.fixture
def report(stub_user_dirs):
    user_data_path, _ = stub_user_dirs

    with all_temporary_images() as (input_path, target_root):
        importer = Importer(
            Path(input_path),
            Path(target_root),
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )
        importer.process_photos()

        report_files = list((user_data_path / "reports").glob("*.html"))
        assert report_files, "Expect a report to have been generated."

        latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
        print(latest_report.read_text(encoding="utf-8"))
        soup = BeautifulSoup(latest_report.read_text(encoding="utf-8"), "html.parser")

        return soup


def test_report_structure(report):
    title = report.find("title")
    assert title is not None, "Report should have a <title> element."
    assert "Fotura" in title.text, f"Unexpected title: {title.text}"

    details_sections = report.find_all("details")
    assert len(details_sections) > 0, "Report should have details sections."

    general_section = None
    for section in details_sections:
        summary = section.find("summary")
        if summary and "Log entries" in clean_text(summary):
            general_section = section
            break

    assert general_section is not None, (
        "Report should have a general log entries section."
    )

    image_sections = [
        section for section in details_sections if section != general_section
    ]

    assert len(image_sections) >= 1, (
        f"Report should have at least one image logs section, found {len(image_sections)}."
    )


def test_report_table_contents(report):
    expected_results = [
        ("IMG-20250521-WA0002.jpg", "Moved to"),
        ("no-date.jpg", "Skipping"),
        ("sony_alpha_a58.JPG", "Moved to"),
        ("date-time-digitized-only.jpg", "Moved to"),
        ("date-time-only.jpg", "Moved to"),
        ("IMG_20100102_030405.jpg", "Moved to"),
        ("IMG_20240909_103402.jpg", "Moved to"),
        ("Canon_40D.jpg", "Moved to"),
        ("Pentax_K10D.jpg", "Moved to"),
    ]

    photo_sections = report.select("#media-logs details")
    assert photo_sections, "Expected photo log sections under #media-logs"

    for filename, expected_action in expected_results:
        matching_sections = [
            section
            for section in photo_sections
            if filename in clean_text(section.find("summary"))
        ]

        assert matching_sections, f"No photo section found for {filename}"

        matched = False
        for section in matching_sections:
            logs = section.select(".log")
            for log in logs:
                if expected_action in clean_text(log):
                    matched = True
                    break
            if matched:
                break

        assert matched, (
            f"No '{expected_action}' log found for {filename}\n"
            f"Actual logs:\n"
            + "\n".join(
                f"- {clean_text(log)}"
                for section in matching_sections
                for log in section.select(".log")
            )
        )
