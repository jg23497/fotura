from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rawpy
from PIL import Image

from fotura.domain.photo import Photo
from fotura.importing.photo_dhash import calculate_dhash


@pytest.mark.parametrize("filename", ["Canon_40D.jpg", "fuji.raf"])
def test_calculate_dhash_supports_standard_and_raw_photos(filename):
    dhash = calculate_dhash(Photo(Path("tests/data") / filename))

    assert 0 <= dhash < 2**64


@pytest.mark.parametrize("extension", ["tif", "tiff"])
def test_calculate_dhash_supports_tiff_photos(tmp_path, extension):
    path = tmp_path / f"photo.{extension}"
    Image.new("RGB", (10, 10), color="red").save(path)

    assert 0 <= calculate_dhash(Photo(path)) < 2**64


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

    with patch("fotura.importing.photo_dhash.rawpy.imread", return_value=raw_context):
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

    with patch("fotura.importing.photo_dhash.rawpy.imread", return_value=raw_context):
        dhash = calculate_dhash(Photo(path))

    assert dhash == 0
