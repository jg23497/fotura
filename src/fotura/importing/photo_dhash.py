from io import BytesIO
from typing import Any, cast

import rawpy
from PIL import Image, ImageOps

from fotura.domain.photo import Photo
from fotura.importing.media_finder import PHOTO_RAW_EXTENSIONS

DHASH_WIDTH = 9
DHASH_HEIGHT = 8


def calculate_dhash(photo: Photo) -> int:
    image = (
        __open_raw(photo)
        if photo.path.suffix.lower() in PHOTO_RAW_EXTENSIONS
        else Image.open(photo.path)
    )

    with image:
        grayscale = ImageOps.exif_transpose(image).convert("L")
        resized = grayscale.resize(
            (DHASH_WIDTH, DHASH_HEIGHT), Image.Resampling.LANCZOS
        )
        pixels = resized.tobytes()

    dhash = 0
    for row in range(DHASH_HEIGHT):
        row_start = row * DHASH_WIDTH
        for column in range(DHASH_WIDTH - 1):
            dhash <<= 1
            dhash |= pixels[row_start + column] > pixels[row_start + column + 1]
    return dhash


def __open_raw(photo: Photo) -> Image.Image:
    with rawpy.imread(str(photo.path)) as raw:
        try:
            thumbnail = raw.extract_thumb()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            return Image.fromarray(raw.postprocess(half_size=True, output_bps=8))

    if thumbnail.format is rawpy.ThumbFormat.JPEG:
        image = Image.open(BytesIO(thumbnail.data))
        image.load()
        return image
    return Image.fromarray(cast(Any, thumbnail.data))
