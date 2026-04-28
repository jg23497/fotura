from pathlib import Path

from fotura.importer import Importer
from tests.helpers.helper import all_temporary_images, assert_exif_dates, get_all_files


def test_photo_sorting():
    with all_temporary_images() as (
        input_path,
        target_root,
    ):
        importer = Importer(
            Path(input_path),
            Path(target_root),
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        results = []
        for file in get_all_files(path=target_root):
            relative_path = Path(file).relative_to(target_root)
            results.append(str(relative_path).replace("\\", "/"))

        assert set(results) == {
            "2008/2008-05/Canon_40D.jpg",
            "2008/2008-05/Pentax_K10D.jpg",
            "2008/2008-05/Pentax_K10D_1.jpg",
            "2010/2010-01/IMG_20100102_030405.jpg",
            "2011/2011-12/date-time-digitized-only.jpg",
            "2011/2011-12/date-time-only.jpg",
            "2023/2023-10/sony_alpha_a58.JPG",
            "2025/2025-05/IMG-20250521-WA0002.jpg",
            "2024/2024-09/IMG_20240909_103402.jpg",
            "2011/2011-05/fuji.raf",
            "2004/2004-03/fuji_s2pro.raf",
        }

        whatsapp_image_path = (
            Path(target_root) / "2025" / "2025-05" / "IMG-20250521-WA0002.jpg"
        )
        assert_exif_dates(whatsapp_image_path, "2025:05:21 12:00:00")

        android_image_path = (
            Path(target_root) / "2024" / "2024-09" / "IMG_20240909_103402.jpg"
        )
        assert_exif_dates(android_image_path, "2024:09:09 10:34:02")


def test_tally_counts():
    with all_temporary_images() as (
        input_path,
        target_root,
    ):
        importer = Importer(
            Path(input_path),
            Path(target_root),
            enabled_before_each_processors=[("filename_timestamp_extract", {})],
        )

        importer.process_photos()

        tally_snapshot = importer.tally.get_snapshot()

        assert tally_snapshot.get("moved") == 11
        assert tally_snapshot.get("skipped") == 1
        assert tally_snapshot.get("errored") == 0
