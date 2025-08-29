from pathlib import Path
from os import scandir
import tempfile
import shutil
import piexif

from photo_tidy.sorter import PhotoSorter

TEST_DIR = Path(__file__).resolve().parent
print(TEST_DIR)
input_directory_path = TEST_DIR / "data"


def test_photo_sorting():
    # Create temporary directories for both input and output
    with (
        tempfile.TemporaryDirectory() as input_temp_dir,
        tempfile.TemporaryDirectory() as target_temp_dir,
    ):
        # Copy all files from test data to input temporary directory recursively
        shutil.copytree(input_directory_path, input_temp_dir, dirs_exist_ok=True)

        print(f"Input directory path: {input_temp_dir}")
        print(f"Temporary directory path: {target_temp_dir}")

        sorter = PhotoSorter(
            Path(input_temp_dir),
            Path(target_temp_dir),
            enabled_preprocessors=[("whatsapp", {})],
        )
        sorter.process_photos()

        print("Contents of temporary directory:")
        results = []
        for f in get_all_files(path=target_temp_dir):
            # Convert to Path and get the relative path from the temporary directory
            relative_path = Path(f).relative_to(target_temp_dir)
            # Use forward slashes for consistency across platforms
            results.append(str(relative_path).replace("\\", "/"))

        print(results)

        assert set(results) == {
            "2008/2008-05/Pentax_K10D.jpg",
            "2008/2008-05/Pentax_K10D_1.jpg",
            "2023/2023-10/sony_alpha_a58.JPG",
            "2008/2008-05/Canon_40D.jpg",
            "2025/2025-05/IMG-20250521-WA0002.jpg",
        }

        # Verify EXIF date data for WhatsApp image
        whatsapp_image_path = (
            Path(target_temp_dir) / "2025" / "2025-05" / "IMG-20250521-WA0002.jpg"
        )
        exif_dict = piexif.load(str(whatsapp_image_path))

        # Check DateTimeOriginal
        date_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode("utf-8")
        assert date_str == "2025:05:21 04:00:00"

        # Check DateTimeDigitized
        date_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized].decode("utf-8")
        assert date_str == "2025:05:21 04:00:00"

        # Check DateTime
        date_str = exif_dict["0th"][piexif.ImageIFD.DateTime].decode("utf-8")
        assert date_str == "2025:05:21 04:00:00"


def get_all_files(path="."):
    with scandir(path) as entries:
        for entry in entries:
            if entry.is_file():
                yield (entry.path)
            elif entry.is_dir():
                yield from get_all_files(entry.path)
