from pathlib import Path

from photo_tidy.tidy import Tidy
from tests.helpers.helper import get_all_files, all_temporary_images, verify_exif_dates


def test_photo_sorting():
    with all_temporary_images() as (
        input_path,
        target_root,
    ):
        tidy = Tidy(
            Path(input_path),
            Path(target_root),
            enabled_preprocessors=[("filename_timestamp_extract", {})],
        )

        tidy.process_photos()

        results = []
        for file in get_all_files(path=target_root):
            relative_path = Path(file).relative_to(target_root)
            results.append(str(relative_path).replace("\\", "/"))

        assert set(results) == {
            "2010/2010-01/IMG_20100102_030405.jpg",
            "2008/2008-05/Pentax_K10D.jpg",
            "2008/2008-05/Pentax_K10D_1.jpg",
            "2023/2023-10/sony_alpha_a58.JPG",
            "2008/2008-05/Canon_40D.jpg",
            "2025/2025-05/IMG-20250521-WA0002.jpg",
            "2024/2024-09/IMG_20240909_103402.jpg",
        }

        whatsapp_image_path = (
            Path(target_root) / "2025" / "2025-05" / "IMG-20250521-WA0002.jpg"
        )
        verify_exif_dates(whatsapp_image_path, "2025:05:21 12:00:00")

        android_image_path = (
            Path(target_root) / "2024" / "2024-09" / "IMG_20240909_103402.jpg"
        )
        verify_exif_dates(android_image_path, "2024:09:09 10:34:02")
