from typing import Any

from fotura.domain.photo_cluster import PhotoCluster


class PhotoClusterReport:
    def __init__(self, photo_clusters: list[PhotoCluster]) -> None:
        self.__photo_clusters = photo_clusters

    def build_entries(
        self, file_entries: dict[str, list[Any]]
    ) -> tuple[list[dict[str, Any]], set[str]]:
        clustered_entries = []
        clustered_paths = set()
        visual_clusters = [
            cluster for cluster in self.__photo_clusters if len(cluster.photos) > 1
        ]

        for index, cluster in enumerate(visual_clusters, start=1):
            photos = []
            previous_photo = None
            for photo in cluster.photos:
                path = str(photo.original_path)
                distance = (
                    cluster.dhash_distances.get(previous_photo, {}).get(photo)
                    if previous_photo is not None
                    else None
                )

                photos.append(
                    {
                        "path": path,
                        "records": file_entries.get(path, []),
                        "dhash_distance": distance,
                    }
                )
                clustered_paths.add(path)
                previous_photo = photo

            clustered_entries.append({"number": index, "photos": photos})

        return clustered_entries, clustered_paths
