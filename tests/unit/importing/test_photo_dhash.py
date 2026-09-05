import logging
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rawpy
from PIL import Image

from fotura.domain.photo import Photo
from fotura.importing.photo_dhash import calculate_dhash
from fotura.importing.photo_thumbnailer import generate_thumbnail


@pytest.mark.parametrize("filename", ["Canon_40D.jpg", "fuji.raf"])
def test_calculate_dhash_supports_standard_and_raw_photos(filename):
    photo = Photo(Path("tests/data") / filename)

    dhash = calculate_dhash(photo)

    assert dhash is not None
    assert 0 <= dhash < 2**64
    assert photo.thumbnail is None


@pytest.mark.parametrize("filename", ["Canon_40D.jpg", "fuji.raf"])
def test_generate_thumbnail_generates_dhash_and_jpeg(filename):
    thumbnail = generate_thumbnail(
        Photo(Path("tests/data") / filename),
        generate_jpeg=True,
        generate_dhash=True,
    )

    assert thumbnail.dhash is not None
    assert 0 <= thumbnail.dhash < 2**64
    assert thumbnail.jpeg is not None
    assert thumbnail.jpeg.startswith(b"\xff\xd8")


def test_generate_thumbnail_generates_only_a_jpeg_when_requested():
    thumbnail = generate_thumbnail(
        Photo(Path("tests/data/Canon_40D.jpg")),
        generate_jpeg=True,
        generate_dhash=False,
    )

    assert thumbnail.dhash is None
    assert thumbnail.jpeg is not None


def test_generate_thumbnail_requires_an_output():
    with pytest.raises(ValueError, match="At least one thumbnail output"):
        generate_thumbnail(
            Photo(Path("tests/data/Canon_40D.jpg")),
            generate_jpeg=False,
            generate_dhash=False,
        )


def test_generate_thumbnail_returns_empty_result_when_generation_fails(caplog):
    with caplog.at_level(logging.ERROR):
        thumbnail = generate_thumbnail(
            Photo(Path("tests/data/invalid.jpg")),
            generate_jpeg=True,
            generate_dhash=True,
        )

    assert thumbnail.jpeg is None
    assert thumbnail.dhash is None
    assert "Thumbnail generation failed" in caplog.text


@pytest.mark.parametrize("extension", ["tif", "tiff"])
def test_calculate_dhash_supports_tiff_photos(tmp_path, extension):
    path = tmp_path / f"photo.{extension}"
    Image.new("RGB", (10, 10), color="red").save(path)

    dhash = calculate_dhash(Photo(path))

    assert dhash is not None
    assert 0 <= dhash < 2**64


def test_calculate_dhash_returns_expected_hash_for_descending_rows(tmp_path):
    path = tmp_path / "descending.tiff"
    image = Image.new("L", (9, 8))
    image.putdata(list(range(8, -1, -1)) * 8)
    image.save(path)

    assert calculate_dhash(Photo(path)) == 2**64 - 1


def test_calculate_dhash_postprocesses_raw_without_a_thumbnail(tmp_path):
    path = tmp_path / "photo.raw"
    raw = Mock()
    raw.extract_thumb.side_effect = rawpy.LibRawNoThumbnailError()
    raw.postprocess.return_value = np.zeros((8, 9, 3), dtype=np.uint8)
    raw_context = Mock()
    raw_context.__enter__ = Mock(return_value=raw)
    raw_context.__exit__ = Mock(return_value=False)

    with patch(
        "fotura.importing.photo_thumbnailer.rawpy.imread", return_value=raw_context
    ):
        calculate_dhash(Photo(path))

    raw.postprocess.assert_called_once_with(half_size=True, output_bps=8)


def test_calculate_dhash_uses_a_raw_bitmap_thumbnail(tmp_path):
    path = tmp_path / "photo.raw"
    raw = Mock()
    raw.extract_thumb.return_value = rawpy.Thumbnail(
        format=rawpy.ThumbFormat.BITMAP,
        data=np.zeros((8, 9, 3), dtype=np.uint8),
    )
    raw_context = Mock()
    raw_context.__enter__ = Mock(return_value=raw)
    raw_context.__exit__ = Mock(return_value=False)

    with patch(
        "fotura.importing.photo_thumbnailer.rawpy.imread", return_value=raw_context
    ):
        dhash = calculate_dhash(Photo(path))

    assert dhash == 0
