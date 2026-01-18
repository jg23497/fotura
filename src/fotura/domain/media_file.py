import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fotura.processors.fact_type import FactType

logger = logging.getLogger(__name__)


class MediaFile:
    def __init__(self, path: Path):
        self.path = path
        self.original_path = path
        self.target_path: Optional[Path] = None
        self.facts: Dict[FactType, Any] = {}

    def log(self, level, msg, *args, **kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("media_file", self.original_path)
        return logger.log(level, msg, *args, **kwargs)
