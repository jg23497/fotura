from pathlib import Path
from typing import Any, Dict, Optional

from fotura.processors.fact_type import FactType


class Photo:
    def __init__(self, path: Path):
        self.path = path
        self.target_path: Optional[Path] = None
        self.facts: Dict[FactType, Any] = {}
