from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, get_ident

from fotura.domain.photo import Photo
from fotura.domain.photo_cluster import PhotoCluster
from fotura.domain.photo_thumbnail import PhotoThumbnail
from fotura.importing.photo_clusterer import PhotoClusterer
from fotura.processors.fact_type import FactType


def photo_with_timestamp(name: str, timestamp: datetime) -> Photo:
    photo = Photo(Path(name))
    photo.facts[FactType.TAKEN_TIMESTAMP] = timestamp
    return photo


def thumbnail_generator_using(calculate_dhash):
    def generate(photo, *, generate_jpeg, generate_dhash):
        assert generate_jpeg is True
        assert generate_dhash is True
        return PhotoThumbnail(
            dhash=calculate_dhash(photo),
            jpeg=b"thumbnail",
        )

    return generate


def test_cluster_returns_no_clusters_when_there_are_no_photos():
    assert PhotoClusterer().cluster([]) == []


def test_cluster_returns_each_photo_in_a_singleton_cluster():
    photos = [Photo(Path("first.jpg")), Photo(Path("second.jpg"))]

    clusters = PhotoClusterer().cluster(photos)

    assert clusters == [
        PhotoCluster(photos=[photos[0]]),
        PhotoCluster(photos=[photos[1]]),
    ]


def test_cluster_sorts_and_clusters_visually_similar_photos():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 20))
    third = photo_with_timestamp("third.jpg", datetime(2026, 1, 1, 10, 1, 0))
    clusterer = PhotoClusterer(
        thumbnail_generator=thumbnail_generator_using(lambda _: 1)
    )

    clusters = clusterer.cluster([third, second, first])

    assert clusters == [
        PhotoCluster(photos=[first, second], dhash_distances={first: {second: 0}}),
        PhotoCluster(photos=[third]),
    ]


def test_cluster_does_not_cluster_temporally_close_but_visually_different_photos():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 1))
    hashes = {first: 0, second: 0b11}
    clusterer = PhotoClusterer(
        max_dhash_distance=1,
        thumbnail_generator=thumbnail_generator_using(hashes.__getitem__),
    )

    clusters = clusterer.cluster([first, second])

    assert clusters == [
        PhotoCluster(photos=[first]),
        PhotoCluster(photos=[second]),
    ]


def test_cluster_only_calculates_dhashes_for_multi_photo_candidate_groups():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 30))
    singleton = photo_with_timestamp("singleton.jpg", datetime(2026, 1, 1, 11, 0, 0))
    hashed_photos = []

    def calculate(photo):
        hashed_photos.append(photo)
        return 42

    PhotoClusterer(thumbnail_generator=thumbnail_generator_using(calculate)).cluster(
        [first, second, singleton]
    )

    assert hashed_photos == [first, second]
    assert first.dhash == second.dhash == 42
    assert first.thumbnail == second.thumbnail == b"thumbnail"
    assert singleton.dhash is None
    assert singleton.thumbnail is None


def test_cluster_calculates_required_dhashes_concurrently():
    photos = [
        photo_with_timestamp(
            f"{index}.jpg", datetime(2026, 1, 1) + timedelta(seconds=index)
        )
        for index in range(2)
    ]
    barrier = Barrier(len(photos))
    worker_thread_ids = []

    def calculate(_):
        worker_thread_ids.append(get_ident())
        barrier.wait(timeout=1)
        return 42

    PhotoClusterer(
        concurrency=2,
        thumbnail_generator=thumbnail_generator_using(calculate),
    ).cluster(photos)

    assert len(set(worker_thread_ids)) == 2
    assert all(photo.dhash == 42 for photo in photos)


def test_cluster_reuses_an_existing_dhash():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 1))
    first.dhash = 42
    hashed_photos = []

    def calculate(photo):
        hashed_photos.append(photo)
        return 42

    clusters = PhotoClusterer(
        thumbnail_generator=thumbnail_generator_using(calculate)
    ).cluster([first, second])

    assert hashed_photos == [second]
    assert clusters == [
        PhotoCluster(photos=[first, second], dhash_distances={first: {second: 0}})
    ]


def test_cluster_respects_a_custom_time_gap():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 6))

    clusters = PhotoClusterer(max_time_gap=timedelta(seconds=5)).cluster(
        [first, second]
    )

    assert clusters == [
        PhotoCluster(photos=[first]),
        PhotoCluster(photos=[second]),
    ]
    assert first.dhash is None
    assert second.dhash is None


def test_cluster_accepts_a_dhash_distance_equal_to_the_threshold():
    first = photo_with_timestamp("first.jpg", datetime(2026, 1, 1, 10, 0, 0))
    second = photo_with_timestamp("second.jpg", datetime(2026, 1, 1, 10, 0, 1))
    hashes = {first: 0, second: 0b11}

    clusters = PhotoClusterer(
        max_dhash_distance=2,
        thumbnail_generator=thumbnail_generator_using(hashes.__getitem__),
    ).cluster([first, second])

    assert clusters == [
        PhotoCluster(photos=[first, second], dhash_distances={first: {second: 2}})
    ]


def test_cluster_records_each_adjacent_distance_in_a_photo_chain():
    photos = [
        photo_with_timestamp(f"{index}.jpg", datetime(2026, 1, 1, 10, 0, index))
        for index in range(3)
    ]
    hashes = {photos[0]: 0b00, photos[1]: 0b01, photos[2]: 0b11}

    clusters = PhotoClusterer(
        max_dhash_distance=1,
        thumbnail_generator=thumbnail_generator_using(hashes.__getitem__),
    ).cluster(photos)

    assert clusters == [
        PhotoCluster(
            photos=photos,
            dhash_distances={
                photos[0]: {photos[1]: 1},
                photos[1]: {photos[2]: 1},
            },
        )
    ]
