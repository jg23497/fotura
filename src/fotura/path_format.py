from datetime import datetime
from pathlib import Path


class PathFormat:
    VALID_DIRECTIVES = {
        "a",
        "A",
        "w",
        "d",
        "b",
        "B",
        "m",
        "y",
        "Y",
        "H",
        "I",
        "p",
        "M",
        "S",
        "f",
        "z",
        "Z",
        "j",
        "U",
        "W",
        "c",
        "x",
        "X",
        "%",
    }

    @staticmethod
    def is_valid(path_format: str) -> bool:
        it = iter(path_format)

        for _, character in enumerate(it):
            if character != "%":
                continue

            next_character = next(it, None)
            # % must be followed by one of the directives
            if next_character is None:
                return False

            if next_character not in PathFormat.VALID_DIRECTIVES:
                return False

        return True

    @staticmethod
    def build_path(root: Path, timestamp: datetime, format: str) -> Path:
        formatted = timestamp.strftime(format)
        return root.joinpath(*formatted.split("/"))
