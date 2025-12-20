from pathlib import Path
from typing import Optional, Set

from fotura.conflict_resolution.strategy_base import StrategyBase


class SkipStrategy(StrategyBase):
    def resolve(
        self,
        target_path: Path,
        claimed_paths: Set[Path],
    ) -> Optional[Path]:
        return None
