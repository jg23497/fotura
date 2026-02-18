from enum import Enum, auto


class FactType(Enum):
    TAKEN_TIMESTAMP = auto()
    IMAGE_DIMENSIONS = auto()
    HASH_BLAKE2B = auto()
