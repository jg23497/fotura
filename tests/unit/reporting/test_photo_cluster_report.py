from pathlib import Path

from fotura.domain.photo import Photo
from fotura.domain.photo_cluster import PhotoCluster
from fotura.reporting.photo_cluster_report import PhotoClusterReport


def test_build_entries_uses_distances_stored_on_cluster():
    first = Photo(Path("first.jpg"))
    second = Photo(Path("second.jpg"))
    cluster = PhotoCluster(
        photos=[first, second],
        dhash_distances={first: {second: 7}},
    )

    entries, clustered_paths = PhotoClusterReport([cluster]).build_entries({})

    assert entries[0]["photos"][0]["dhash_distance"] is None
    assert entries[0]["photos"][1]["dhash_distance"] == 7
    assert clustered_paths == {"first.jpg", "second.jpg"}


def test_build_entries_excludes_single_photo_clusters():
    photo = Photo(Path("single.jpg"))

    entries, clustered_paths = PhotoClusterReport(
        [PhotoCluster(photos=[photo])]
    ).build_entries({})

    assert entries == []
    assert clustered_paths == set()


def test_build_entries_numbers_multiple_visual_clusters():
    photos = [Photo(Path(f"{index}.jpg")) for index in range(4)]
    clusters = [
        PhotoCluster(photos=photos[:2]),
        PhotoCluster(photos=photos[2:]),
    ]

    entries, clustered_paths = PhotoClusterReport(clusters).build_entries({})

    assert [entry["number"] for entry in entries] == [1, 2]
    assert clustered_paths == {str(photo.path) for photo in photos}
