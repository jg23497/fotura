import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fotura.processors.fact_type import FactType

logger = logging.getLogger(__name__)


class Photo:
    def __init__(self, path: Path):
        self.path = path
        self.target_path: Optional[Path] = None
        self.facts: Dict[FactType, Any] = {}

    def log(self, level, msg, *args, **kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("photo", self.path)
        return logger.log(level, msg, *args, **kwargs)
