import pytest
from pathlib import Path

from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from photo_tidy.reporting.report import Report


@pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".txt.jpg"])
def test_can_handle_returns_true_when_file_extension_is_in_supported_list(extension):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)
    assert processor.can_handle(Path(f"foo{extension}")), (
        f"Should handle extension: {extension}"
    )


@pytest.mark.parametrize("extension", [None, "", ".txt", ".mp4"])
def test_can_handle_returns_false_when_file_extension_is_not_supported(extension):
    report = Report()
    processor = GooglePhotosUploadPostprocessor(report)
    assert not processor.can_handle(Path(f"Foo{extension}")), (
        f"Should not handle extension: {extension}"
    )
