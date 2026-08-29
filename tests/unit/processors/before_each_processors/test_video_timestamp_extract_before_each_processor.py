import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fotura.domain.photo import Photo
from fotura.persistence.database import Database
from fotura.processors.before_each_processors.video_timestamp_extract_before_each_processor import (
    QUICKTIME_EPOCH,
    VideoTimestampExtractBeforeEachProcessor,
)
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.utils.synchronized_counter import SynchronizedCounter
from tests.helpers.helper import temporary_images


@pytest.fixture
def processor(tmp_path):
    context = Context(
        user_config_path=tmp_path,
        tally=SynchronizedCounter({"errored": 0}),
        dry_run=False,
        database=Database(),
    )
    return VideoTimestampExtractBeforeEachProcessor(context)


@pytest.mark.parametrize("extension", ["mp4", "MP4", "m4v", "mov", "3gp", "3g2"])
def test_can_handle_iso_media_video_extensions(processor, extension):
    assert processor.can_handle(Photo(Path(f"video.{extension}"))) is True


def test_can_handle_rejects_other_extensions(processor):
    assert processor.can_handle(Photo(Path("video.avi"))) is False


@pytest.mark.parametrize("version", [0, 1])
def test_process_extracts_movie_header_creation_timestamp(processor, tmp_path, version):
    expected = datetime(2024, 7, 6, 12, 34, 56)
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(__video_with_creation_time(expected, version))

    result = processor.process(Photo(video_path))

    assert result == {FactType.TAKEN_TIMESTAMP: expected}


def test_process_supports_extended_size_boxes(processor, tmp_path):
    expected = datetime(2020, 1, 2, 3, 4, 5)
    video_path = tmp_path / "video.mov"
    mvhd = __box(b"mvhd", __movie_header(expected, 0), extended=True)
    video_path.write_bytes(__box(b"moov", mvhd, extended=True))

    assert processor.process(Photo(video_path)) == {FactType.TAKEN_TIMESTAMP: expected}


def test_process_returns_none_for_non_video(processor):
    assert processor.process(Photo(Path("photo.jpg"))) is None


def test_process_returns_none_when_movie_header_has_no_timestamp(
    processor, tmp_path, caplog
):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(__box(b"moov", __box(b"free", b"content")))

    result = processor.process(Photo(video_path))

    assert result is None
    assert "video file may be invalid or mislabeled" in caplog.text


def test_process_handles_jpeg_with_mp4_extension(processor, caplog):
    with temporary_images(["Canon_40D.jpg"]) as (_, _, input_image_paths):
        video_path = input_image_paths[0].with_suffix(".mp4")
        input_image_paths[0].rename(video_path)

        result = processor.process(Photo(video_path))

        assert result is None
        assert "video file may be invalid or mislabeled" in caplog.text


def test_process_handles_corrupt_video_file(processor, tmp_path, caplog):
    video_path = tmp_path / "corrupt.mp4"
    video_path.write_bytes(b"not a video")

    result = processor.process(Photo(video_path))

    assert result is None
    assert "video file may be invalid or mislabeled" in caplog.text


def __video_with_creation_time(timestamp: datetime, version: int) -> bytes:
    return __box(b"ftyp", b"isom") + __box(
        b"moov", __box(b"mvhd", __movie_header(timestamp, version))
    )


def __movie_header(timestamp: datetime, version: int) -> bytes:
    seconds = int(
        (timestamp.replace(tzinfo=timezone.utc) - QUICKTIME_EPOCH).total_seconds()
    )
    encoded = struct.pack(">Q" if version == 1 else ">I", seconds)
    return bytes([version, 0, 0, 0]) + encoded


def __box(box_type: bytes, payload: bytes, extended: bool = False) -> bytes:
    if extended:
        return struct.pack(">I4sQ", 1, box_type, 16 + len(payload)) + payload
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload
