from pathlib import Path
from typing import Set


class ConflictResolutionStrategy:
    def resolve(
        self,
        target_path: Path,
        claimed_paths: Set[Path],
    ) -> Path:
        raise NotImplementedError
