from pathlib import Path
from typing import Set

from photo_tidy.conflict_resolution.strategy_base import ConflictResolutionStrategy


class KeepBothStrategy(ConflictResolutionStrategy):
    def resolve(
        self,
        target_path: Path,
        claimed_paths: Set[Path],
    ) -> Path:
        target_dir = target_path.parent
        base_name = target_path.stem
        extension = target_path.suffix

        counter = 1
        while target_path in claimed_paths or target_path.exists():
            target_path = target_dir / f"{base_name}_{counter}{extension}"
            counter += 1

        return target_path
