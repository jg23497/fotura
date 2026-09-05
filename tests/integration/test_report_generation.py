import shutil
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Optional

import pytest
from bs4 import BeautifulSoup, Tag

from fotura.domain.photo import Photo
from fotura.domain.photo_cluster import PhotoCluster
from fotura.importer import Importer
from fotura.reporting.logging_config import HTMLReportHandler
from fotura.utils.synchronized_counter import SynchronizedCounter
from tests.helpers.helper import all_temporary_images


def clean_text(element: Optional[Tag]) -> str:
    if element is None:
        return ""
    return element.get_text(separator=" ", strip=True)


@dataclass
class ClusteredReport:
    report: BeautifulSoup
    cluster_section: Tag
    filenames: list[str]


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

    report_version = report.select_one(".report-version")
    assert report_version is not None
    assert f"Fotura v{version('fotura')}" in clean_text(report_version)

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
    assert not ignored_section.has_attr("open")
    assert not skipped_section.has_attr("open")

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


@pytest.fixture
def clustered_report(stub_user_dirs, tmp_path) -> ClusteredReport:
    user_data_path, _ = stub_user_dirs
    input_path = tmp_path / "input"
    target_root = tmp_path / "target"
    input_path.mkdir()
    source = Path("tests/data/Canon_40D.jpg")
    filenames = ["IMG_20260101_100000.jpg", "IMG_20260101_100001.jpg"]
    for filename in filenames:
        shutil.copy2(source, input_path / filename)

    importer = Importer(
        input_path,
        target_root,
        dry_run=True,
        enabled_before_each_processors=[("filename_timestamp_extract", {})],
        cluster_photos=True,
    )
    importer.process_media_files()

    report_path = next((user_data_path / "reports").glob("*.html"))
    report = BeautifulSoup(report_path.read_text(encoding="utf-8"), "html.parser")
    cluster_section = report.select_one("#photo-cluster-logs .photo-cluster")
    assert isinstance(cluster_section, Tag)

    return ClusteredReport(
        report=report,
        cluster_section=cluster_section,
        filenames=filenames,
    )


def test_report_summarises_visual_photo_clusters(clustered_report):
    general_logs = clean_text(clustered_report.report.select_one("#general-logs"))

    assert (
        "Photo clustering identified 1 cluster(s) containing 2 photo(s)" in general_logs
    )


def test_report_collapses_visual_photo_clusters_by_default(clustered_report):
    cluster_section = clustered_report.cluster_section

    assert not cluster_section.has_attr("open")
    assert "Photo cluster 1 (2026/01/01) — 2 photos" in clean_text(
        cluster_section.find("summary", recursive=False)
    )


def test_report_displays_clustered_photos_and_dhash_distance(clustered_report):
    cluster_section = clustered_report.cluster_section
    cluster_text = clean_text(cluster_section)

    assert all(filename in cluster_text for filename in clustered_report.filenames)
    assert "dHash distance: 0" in cluster_text
    assert "Moved to" in cluster_text


def test_report_displays_clustered_photo_thumbnails(clustered_report):
    thumbnails = clustered_report.cluster_section.select("img.cluster-thumbnail")

    assert len(thumbnails) == 2
    assert all(
        thumbnail.get("src", "").startswith("data:image/jpeg;base64,")
        for thumbnail in thumbnails
    )
    assert (
        clustered_report.cluster_section.select_one(".cluster-thumbnail-placeholder")
        is None
    )


def test_report_removes_clustered_photos_from_flat_file_list(clustered_report):
    standalone_files = " ".join(
        clean_text(summary)
        for summary in clustered_report.report.select(
            "#media-logs > .media-logs > details > summary"
        )
    )

    for filename in clustered_report.filenames:
        assert filename not in standalone_files


def test_report_omits_photo_cluster_section_when_clustering_is_disabled(report):
    assert report.select_one("#photo-cluster-logs") is None


def test_report_explains_when_clustering_finds_no_visual_clusters(tmp_path):
    output_path = tmp_path / "report.html"
    handler = HTMLReportHandler(output_path)
    handler.set_photo_clusters([])

    handler.close()

    report = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
    cluster_section = report.select_one("#photo-cluster-logs")

    assert cluster_section is not None
    assert "No visual photo clusters identified." in clean_text(cluster_section)
    assert cluster_section.select_one(".photo-cluster") is None


def test_report_displays_placeholder_when_cluster_thumbnail_is_missing(tmp_path):
    output_path = tmp_path / "report.html"
    handler = HTMLReportHandler(output_path)

    first = Photo(Path("first.jpg"))
    second = Photo(Path("second.jpg"))

    handler.set_photo_clusters(
        [
            PhotoCluster(
                photos=[first, second],
                dhash_distances={first: {second: 0}},
            )
        ]
    )

    handler.close()

    report = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
    placeholders = report.select(".cluster-thumbnail-placeholder")

    assert len(placeholders) == 2
    assert "Photo cluster 1 (Unknown date) — 2 photos" in clean_text(
        report.select_one(".photo-cluster > summary")
    )
    assert all(
        clean_text(placeholder) == "No thumbnail" for placeholder in placeholders
    )


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
    attribute_names = []
    for card in attribute_cards:
        name_elem = card.select_one(".attribute-name")
        value_elem = card.select_one(".attribute-value")
        if name_elem and value_elem:
            name = clean_text(name_elem).strip()
            value = clean_text(value_elem).strip()
            attribute_names.append(name)
            attributes[name] = value

    assert attribute_names == ["errored", "ignored", "skipped", "moved"]
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


def test_report_preserves_processor_tally_cards_after_core_cards(tmp_path):
    output_path = tmp_path / "report.html"
    handler = HTMLReportHandler(output_path)

    handler.close(
        SynchronizedCounter({"errored": 0, "moved": 2, "uploaded to google photos": 2})
    )

    report = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
    cards = [
        (
            clean_text(card.select_one(".attribute-name")),
            clean_text(card.select_one(".attribute-value")),
        )
        for card in report.select(".summary-attribute-card")
    ]
    assert cards == [
        ("errored", "0"),
        ("ignored", "0"),
        ("skipped", "0"),
        ("moved", "2"),
        ("uploaded to google photos", "2"),
    ]
