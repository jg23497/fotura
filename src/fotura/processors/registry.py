from fotura.processors.after_all_processors.google_photos_upload_after_all_processor import (
    GooglePhotosUploadAfterAllProcessor,
)
from fotura.processors.after_each_processors.google_photos_upload_after_each_processor import (
    GooglePhotosUploadAfterEachProcessor,
)
from fotura.processors.before_each_processors.filename_timestamp_extract_before_each_processor import (
    FilenameTimestampExtractBeforeEachProcessor,
)

BEFORE_EACH_PROCESSOR_MAP = {
    "filename_timestamp_extract": FilenameTimestampExtractBeforeEachProcessor,
}

AFTER_EACH_PROCESSOR_MAP = {
    "google_photos_upload": GooglePhotosUploadAfterEachProcessor
}

AFTER_ALL_PROCESSOR_MAP = {
    "google_photos_upload_batch": GooglePhotosUploadAfterAllProcessor
}
