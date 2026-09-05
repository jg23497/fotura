import logging
from io import BytesIO
from typing import Any, cast

import rawpy
from PIL import Image, ImageOps

from fotura.domain.photo import Photo
from fotura.domain.photo_thumbnail import PhotoThumbnail
from fotura.importing.media_finder import PHOTO_RAW_EXTENSIONS

DHASH_WIDTH = 9
DHASH_HEIGHT = 8

THUMBNAIL_SIZE = (240, 240)


def generate_thumbnail(
    photo: Photo,
    *,
    generate_jpeg: bool,
    generate_dhash: bool,
) -> PhotoThumbnail:
    if not generate_jpeg and not generate_dhash:
        raise ValueError("At least one thumbnail output must be requested")

    try:
        image = __open_photo(photo)
        with image:
            oriented = ImageOps.exif_transpose(image)
            thumbnail_image = __create_thumbnail_image(oriented)
            dhash = __calculate_dhash(thumbnail_image) if generate_dhash else None
            jpeg = __encode_jpeg(thumbnail_image) if generate_jpeg else None
    except Exception:
        photo.log(logging.ERROR, "Thumbnail generation failed", exc_info=True)
        return PhotoThumbnail()

    return PhotoThumbnail(jpeg=jpeg, dhash=dhash)


def __open_photo(photo: Photo) -> Image.Image:
    if photo.path.suffix.lower() in PHOTO_RAW_EXTENSIONS:
        return __open_raw(photo)

    return Image.open(photo.path)


def __create_thumbnail_image(image: Image.Image) -> Image.Image:
    thumbnail = image.copy()
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

    return thumbnail


def __calculate_dhash(thumbnail: Image.Image) -> int:
    grayscale = thumbnail.convert("L")
    resized = grayscale.resize((DHASH_WIDTH, DHASH_HEIGHT), Image.Resampling.LANCZOS)
    pixels = resized.tobytes()

    dhash = 0
    for row in range(DHASH_HEIGHT):
        row_start = row * DHASH_WIDTH
        for column in range(DHASH_WIDTH - 1):
            dhash <<= 1
            dhash |= pixels[row_start + column] > pixels[row_start + column + 1]

    return dhash


def __encode_jpeg(thumbnail: Image.Image) -> bytes | None:
    try:
        if thumbnail.mode != "RGB":
            thumbnail = thumbnail.convert("RGB")

        output = BytesIO()
        thumbnail.save(output, format="JPEG", quality=75, optimize=True)

        return output.getvalue()
    except (OSError, ValueError):
        return None


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
