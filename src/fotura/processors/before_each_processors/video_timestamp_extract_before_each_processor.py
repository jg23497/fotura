import logging
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Dict, Iterator, Optional, Tuple, TypeGuard

from fotura.domain.media_file import MediaFile
from fotura.domain.video_file import VideoFile
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType

from .before_each_processor import BeforeEachProcessor

QUICKTIME_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


class VideoTimestampExtractBeforeEachProcessor(BeforeEachProcessor[VideoFile]):
    """Extract the creation timestamp from ISO Base Media/QuickTime containers."""

    def __init__(self, context: Context) -> None:
        self.context = context

    def can_handle(self, media_file: MediaFile) -> TypeGuard[VideoFile]:
        return isinstance(media_file, VideoFile)

    def process(self, media_file: VideoFile) -> Optional[Dict[FactType, datetime]]:
        timestamp = self.__extract_timestamp(media_file.path)
        if timestamp is None:
            media_file.log(
                logging.WARNING,
                "Unable to extract video timestamp; video file may be invalid or mislabeled",
            )
            return None

        media_file.log(
            logging.INFO,
            "Extracted video creation timestamp %s",
            timestamp.strftime("%Y/%m/%d %H:%M:%S"),
        )
        return {FactType.TAKEN_TIMESTAMP: timestamp}

    def __extract_timestamp(self, path: Path) -> Optional[datetime]:
        with path.open("rb") as video:
            video.seek(0, 2)
            file_end = video.tell()
            for box_type, payload_start, box_end in self.__boxes(video, 0, file_end):
                if box_type != b"moov":
                    continue
                for child_type, child_start, child_end in self.__boxes(
                    video, payload_start, box_end
                ):
                    if child_type == b"mvhd":
                        return self.__read_movie_header(video, child_start, child_end)
        return None

    def __boxes(
        self, video: BinaryIO, start: int, end: int
    ) -> Iterator[Tuple[bytes, int, int]]:
        position = start
        while position + 8 <= end:
            video.seek(position)
            header = video.read(8)
            size, box_type = struct.unpack(">I4s", header)
            header_size = 8

            if size == 1:
                extended_size = video.read(8)
                if len(extended_size) != 8:
                    return
                size = struct.unpack(">Q", extended_size)[0]
                header_size = 16
            elif size == 0:
                size = end - position

            box_end = position + size
            if size < header_size or box_end > end:
                return

            yield box_type, position + header_size, box_end
            position = box_end

    def __read_movie_header(
        self, video: BinaryIO, payload_start: int, box_end: int
    ) -> Optional[datetime]:
        video.seek(payload_start)
        version_bytes = video.read(4)
        if len(version_bytes) != 4:
            return None

        version = version_bytes[0]
        timestamp_size = 8 if version == 1 else 4 if version == 0 else 0
        if timestamp_size == 0 or payload_start + 4 + timestamp_size > box_end:
            return None

        creation_time_bytes = video.read(timestamp_size)
        creation_time = int.from_bytes(creation_time_bytes, "big")
        if creation_time == 0:
            return None

        try:
            timestamp = QUICKTIME_EPOCH + timedelta(seconds=creation_time)
        except OverflowError:
            return None
        return timestamp.replace(tzinfo=None)
