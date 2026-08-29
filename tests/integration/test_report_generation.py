import logging
from pathlib import Path
from typing import Optional

import pytest
from bs4 import BeautifulSoup, Tag

from fotura.importer import Importer
from fotura.reporting.logging_config import HTMLReportHandler
from fotura.reporting.report_category import ReportCategory
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
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )
        importer.process_media_files()

        report_files = list((user_data_path / "reports").glob("*.html"))
        assert report_files, "Expect a report to have been generated."

        latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
        print(latest_report.read_text(encoding="utf-8"))
        soup = BeautifulSoup(latest_report.read_text(encoding="utf-8"), "html.parser")

        return soup


@pytest.fixture
def dry_run_report(stub_user_dirs):
    user_data_path, _ = stub_user_dirs

    with all_temporary_images() as (input_path, target_root):
        importer = Importer(
            Path(input_path),
            Path(target_root),
            dry_run=True,
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )
        importer.process_media_files()

        report_files = list((user_data_path / "reports").glob("*.html"))
        assert report_files
        latest_report = max(report_files, key=lambda path: path.stat().st_mtime)
        return BeautifulSoup(latest_report.read_text(encoding="utf-8"), "html.parser")


def test_report_structure(report):
    title = report.find("title")
    assert title is not None, "Report should have a <title> element."
    assert "Fotura" in title.text, f"Unexpected title: {title.text}"

    details_sections = report.find_all("details")
    assert len(details_sections) > 0, "Report should have details sections."

    general_section = None
    for section in details_sections:
        summary = section.find("summary")
        if summary and clean_text(summary) == "General":
            general_section = section
            break

    assert general_section is not None, (
        "Report should have a general log entries section."
    )
    assert "Disk space check:" in clean_text(general_section)

    skipped_section = report.select_one("#skipped-logs details")
    assert skipped_section is not None, "Report should have a skipped entries section."

    ignored_section = report.select_one("#ignored-logs details")
    assert ignored_section is not None, "Report should have an ignored entries section."
    assert ignored_section.has_attr("open")
    assert skipped_section.has_attr("open")

    assert report.select_one("#general-logs > .section-separator") is not None
    assert report.select_one("#skipped-logs > .section-separator") is not None
    assert report.select_one("#ignored-logs > .section-separator") is not None

    top_level_section_ids = [
        section.get("id")
        for section in report.body.find_all("div", recursive=False)
        if section.get("id") in {"general-logs", "ignored-logs", "skipped-logs"}
    ]
    assert top_level_section_ids == ["general-logs", "ignored-logs", "skipped-logs"]

    image_sections = [
        section
        for section in details_sections
        if section not in (general_section, skipped_section, ignored_section)
    ]

    assert len(image_sections) >= 1, (
        f"Report should have at least one image logs section, found {len(image_sections)}."
    )


def test_report_displays_dry_run_indicator_only_for_dry_runs(report, dry_run_report):
    assert report.select_one(".dry-run-indicator") is None

    indicator = dry_run_report.select_one(".dry-run-indicator")

    assert indicator is not None
    assert clean_text(indicator) == "Dry run — no files changed"
    assert indicator.find_previous_sibling("button", id="themeToggle") is not None
    assert "Disk space check:" in clean_text(dry_run_report.select_one("#general-logs"))


def test_report_photo_contents(report):
    expected_results = [
        ("IMG-20250521-WA0002.jpg", "Moved to"),
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

    skipped_section = report.select_one("#skipped-logs")
    assert skipped_section is not None
    assert "no-date.jpg" in clean_text(skipped_section)
    assert "Skipping file: no date found" in clean_text(skipped_section)

    media_logs = report.select_one("#media-logs")
    assert media_logs is not None
    assert "no-date.jpg" not in clean_text(media_logs)

    ignored_section = report.select_one("#ignored-logs")
    assert ignored_section is not None
    assert "test.txt" in clean_text(ignored_section)
    assert "extension not in supported list" in clean_text(ignored_section)
    assert "test.txt" not in clean_text(media_logs)


def test_report_displays_tally_counts(report):
    attributes_section = report.select(".summary-attributes")
    assert attributes_section, "Report should have an attributes section"

    attribute_cards = report.select(".summary-attribute-card")
    assert len(attribute_cards) > 0, "Report should have attribute cards"

    attributes = {}
    for card in attribute_cards:
        name_elem = card.select_one(".attribute-name")
        value_elem = card.select_one(".attribute-value")
        if name_elem and value_elem:
            name = clean_text(name_elem).strip()
            value = clean_text(value_elem).strip()
            attributes[name] = value

    assert "moved" in attributes, "Report should display 'moved' count"
    assert "skipped" in attributes, "Report should display 'skipped' count"
    assert "ignored" in attributes, "Report should display 'ignored' count"
    assert "errored" in attributes, "Report should display 'errored' count"

    assert attributes["moved"] == "11", (
        f"Expected 11 moved files, got {attributes['moved']}"
    )
    assert attributes["skipped"] == "2", (
        f"Expected 2 skipped files, got {attributes['skipped']}"
    )
    assert attributes["ignored"] == "1", (
        f"Expected 1 ignored file, got {attributes['ignored']}"
    )
    assert attributes["errored"] == "0", (
        f"Expected 0 errored files, got {attributes['errored']}"
    )


@pytest.mark.parametrize(
    ("entry_count", "expected_open"),
    [(10, True), (11, False)],
)
def test_report_category_sections_collapse_above_ten_entries(
    tmp_path, entry_count, expected_open
):
    output_path = tmp_path / "report.html"
    handler = HTMLReportHandler(output_path)

    for category in (ReportCategory.ignored, ReportCategory.skipped):
        for index in range(entry_count):
            record = logging.LogRecord(
                name=__name__,
                level=logging.WARNING,
                pathname=__file__,
                lineno=0,
                msg="Categorised file",
                args=(),
                exc_info=None,
            )
            record.media_file = Path(f"file-{category.value}-{index}.jpg")
            record.report_category = category
            handler.emit(record)

    handler.close()

    report = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
    for section_id in ("ignored-logs", "skipped-logs"):
        section = report.select_one(f"#{section_id} details")
        assert section is not None
        assert section.has_attr("open") is expected_open


def test_empty_report_categories_are_collapsed_and_display_zero_counts(tmp_path):
    output_path = tmp_path / "report.html"
    handler = HTMLReportHandler(output_path)

    handler.close()

    report = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
    for section_id in ("ignored-logs", "skipped-logs"):
        section = report.select_one(f"#{section_id} details")
        assert section is not None
        assert not section.has_attr("open")

    attributes = {
        clean_text(card.select_one(".attribute-name")): clean_text(
            card.select_one(".attribute-value")
        )
        for card in report.select(".summary-attribute-card")
    }
    assert attributes["ignored"] == "0"
    assert attributes["skipped"] == "0"
