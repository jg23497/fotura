from pathlib import Path
from typing import Optional, Set

from fotura.importing.conflict_resolution.strategies.strategy_base import StrategyBase


class KeepBothStrategy(StrategyBase):
    def resolve(
        self,
        target_path: Path,
        claimed_paths: Set[Path],
    ) -> Optional[Path]:
        target_directory = target_path.parent
        base_name = target_path.stem
        extension = target_path.suffix

        counter = 1
        while target_path in claimed_paths or target_path.exists():
            target_path = target_directory / f"{base_name}_{counter}{extension}"
            counter += 1

        return target_path
