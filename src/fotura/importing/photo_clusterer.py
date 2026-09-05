from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Callable

from fotura.domain.photo import Photo
from fotura.domain.photo_cluster import PhotoCluster
from fotura.importing.photo_dhash import calculate_dhash
from fotura.processors.fact_type import FactType


class PhotoClusterer:
    def __init__(
        self,
        max_time_gap: timedelta = timedelta(seconds=30),
        max_dhash_distance: int = 20,
        concurrency: int = 1,
        dhash_calculator: Callable[[Photo], int] = calculate_dhash,
    ) -> None:
        self.__max_time_gap = max_time_gap
        self.__max_dhash_distance = max_dhash_distance
        self.__concurrency = concurrency
        self.__dhash_calculator = dhash_calculator

    def cluster(self, photos: list[Photo]) -> list[PhotoCluster]:
        candidate_groups = self.__group_by_time(photos)
        self.__populate_dhashes(self.__photos_to_hash(candidate_groups))
        return self.__cluster_by_visual_similarity(candidate_groups)

    @staticmethod
    def __photos_to_hash(candidate_groups: list[list[Photo]]) -> list[Photo]:
        photos_to_hash = []
        for group in candidate_groups:
            if len(group) == 1:
                continue
            for photo in group:
                if photo.dhash is None:
                    photos_to_hash.append(photo)
        return photos_to_hash

    def __group_by_time(self, photos: list[Photo]) -> list[list[Photo]]:
        timestamped_photos: list[tuple[datetime, Photo]] = []
        photos_without_timestamps: list[Photo] = []

        for photo in photos:
            timestamp = photo.facts.get(FactType.TAKEN_TIMESTAMP)
            if isinstance(timestamp, datetime):
                timestamped_photos.append((timestamp, photo))
            else:
                photos_without_timestamps.append(photo)

        timestamped_photos.sort(key=lambda item: item[0])
        groups: list[list[Photo]] = []
        previous_timestamp: datetime | None = None

        for timestamp, photo in timestamped_photos:
            if (
                previous_timestamp is None
                or timestamp - previous_timestamp > self.__max_time_gap
            ):
                groups.append([])
            groups[-1].append(photo)
            previous_timestamp = timestamp

        groups.extend([[photo] for photo in photos_without_timestamps])
        return groups

    def __populate_dhashes(self, photos: list[Photo]) -> None:
        if self.__concurrency == 1:
            for photo in photos:
                photo.dhash = self.__dhash_calculator(photo)
            return

        with ThreadPoolExecutor(max_workers=self.__concurrency) as executor:
            hashes = executor.map(self.__dhash_calculator, photos)
            for photo, dhash in zip(photos, hashes):
                photo.dhash = dhash

    def __cluster_by_visual_similarity(
        self, candidate_groups: list[list[Photo]]
    ) -> list[PhotoCluster]:
        return [
            cluster
            for candidate_group in candidate_groups
            for cluster in self.__cluster_candidate_group(candidate_group)
        ]

    def __cluster_candidate_group(
        self, candidate_group: list[Photo]
    ) -> list[PhotoCluster]:
        current_cluster = PhotoCluster(photos=[candidate_group[0]])
        clusters = []

        for reference, photo in pairwise(candidate_group):
            distance = self.__dhash_distance(reference, photo)
            if distance is None or distance > self.__max_dhash_distance:
                clusters.append(current_cluster)
                current_cluster = PhotoCluster(photos=[])
            else:
                current_cluster.dhash_distances.setdefault(reference, {})[photo] = (
                    distance
                )
            current_cluster.photos.append(photo)

        clusters.append(current_cluster)
        return clusters

    @staticmethod
    def __dhash_distance(first: Photo, second: Photo) -> int | None:
        if first.dhash is None or second.dhash is None:
            return None
        return (first.dhash ^ second.dhash).bit_count()
