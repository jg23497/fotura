from pathlib import Path
from typing import Optional, Set


class StrategyBase:
    def resolve(
        self,
        target_path: Path,
        claimed_paths: Set[Path],
    ) -> Optional[Path]:
        raise NotImplementedError
