from pathlib import Path

from fotura.domain.photo import Photo


def test_photo_has_no_dhash_by_default():
    photo = Photo(Path("photo.jpg"))

    assert photo.dhash is None


def test_photo_stores_dhash_separately_from_facts():
    photo = Photo(Path("photo.jpg"))

    photo.dhash = 42

    assert photo.dhash == 42
    assert photo.facts == {}
