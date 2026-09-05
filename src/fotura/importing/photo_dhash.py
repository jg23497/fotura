from fotura.domain.photo import Photo
from fotura.importing.photo_thumbnailer import generate_thumbnail


def calculate_dhash(photo: Photo) -> int | None:
    thumbnail = generate_thumbnail(
        photo,
        generate_jpeg=False,
        generate_dhash=True,
    )
    return thumbnail.dhash
