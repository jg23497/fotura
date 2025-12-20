from pathlib import Path
from typing import Iterator

from fotura.reporting import Report, SkippedReportItem


class PhotoFinder:
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".tif", ".arw"}

    def __init__(self, input_path: Path, report: Report):
        self.input_path = input_path
        self.report = report

    def find_photos(self) -> Iterator[Path]:
        for file_path in self.input_path.rglob("*"):
            if not file_path.is_file():
                continue

            file_extension = file_path.suffix.lower()
            if file_extension not in self.SUPPORTED_EXTENSIONS:
                self.report.log(
                    SkippedReportItem(
                        file_path, f"{file_extension} not in supported file extensions"
                    )
                )
                continue

            yield file_path
