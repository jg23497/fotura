from dataclasses import dataclass, field

from fotura.domain.photo import Photo


@dataclass
class PhotoCluster:
    photos: list[Photo]
    dhash_distances: dict[Photo, dict[Photo, int]] = field(default_factory=dict)
