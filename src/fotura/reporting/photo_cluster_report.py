import base64
from datetime import datetime
from typing import Any

from fotura.domain.photo_cluster import PhotoCluster
from fotura.processors.fact_type import FactType


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
                        "thumbnail_data_uri": self.__thumbnail_data_uri(
                            photo.thumbnail
                        ),
                    }
                )
                clustered_paths.add(path)
                previous_photo = photo

            clustered_entries.append(
                {
                    "number": index,
                    "date": self.__cluster_date(cluster),
                    "photos": photos,
                }
            )

        return clustered_entries, clustered_paths

    @staticmethod
    def __thumbnail_data_uri(thumbnail: bytes | None) -> str | None:
        if thumbnail is None:
            return None
        encoded = base64.b64encode(thumbnail).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def __cluster_date(cluster: PhotoCluster) -> str:
        timestamp = cluster.photos[0].facts.get(FactType.TAKEN_TIMESTAMP)
        if not isinstance(timestamp, datetime):
            return "Unknown date"
        return timestamp.strftime("%Y/%m/%d")
