import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fotura.domain.photo import Photo
from fotura.importing.conflict_resolution.strategies.strategy_base import StrategyBase
from fotura.io.path_format import PathFormat
from fotura.io.photos.exif_data import ExifData
from fotura.processors.fact_type import FactType
from fotura.reporting import Report, SkippedReportItem

logger = logging.getLogger(__name__)


class PathResolver:
    def __init__(
        self,
        target_root: Path,
        target_path_format: str,
        conflict_resolver: StrategyBase,
        report: Report,
        dry_run: bool = False,
    ):
        self.target_root = target_root
        self.target_path_format = target_path_format
        self.report = report
        self.dry_run = dry_run
        self.conflict_resolver = conflict_resolver
        self.claimed_paths = set[Path]()

    def get_target_path(self, photo: Photo) -> Optional[Path]:
        date = photo.facts.get(FactType.TAKEN_TIMESTAMP)

        if not date:
            date = ExifData.extract_date(photo.path)
        if not date:
            self.report.log(SkippedReportItem(photo.path, "No date found"))
            return None

        return self.__assign_target_path(date, photo.path)

    def __assign_target_path(
        self, date: datetime, original_path: Path
    ) -> Optional[Path]:
        target_directory = PathFormat.build_path(
            self.target_root, date, self.target_path_format
        )

        if not self.dry_run:
            target_directory.mkdir(parents=True, exist_ok=True)

        target_path = target_directory / f"{original_path.stem}{original_path.suffix}"

        if target_path in self.claimed_paths or target_path.exists():
            target_path = self.conflict_resolver.resolve(
                target_path=target_path,
                claimed_paths=self.claimed_paths,
            )
            if target_path is None:
                self.report.log(
                    SkippedReportItem(original_path, "Conflict resolution strategy")
                )
                return None

        self.claimed_paths.add(target_path)
        return target_path
