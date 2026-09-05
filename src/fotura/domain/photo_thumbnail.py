from dataclasses import dataclass


@dataclass(frozen=True)
class PhotoThumbnail:
    jpeg: bytes | None = None
    dhash: int | None = None
