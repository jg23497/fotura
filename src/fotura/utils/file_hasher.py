import hashlib
from pathlib import Path

BUFFER_SIZE_BYTES = 8192


def hash_file(path: Path) -> str:
    hash = hashlib.blake2b(digest_size=16)

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(BUFFER_SIZE_BYTES), b""):
            hash.update(chunk)

    return hash.hexdigest()
