from fotura.processors.after_all_processors.google_photos_upload_after_all_processor import (
    GooglePhotosUploadAfterAllProcessor,
)
from fotura.processors.before_each_processors.filename_timestamp_extract_before_each_processor import (
    FilenameTimestampExtractBeforeEachProcessor,
)
from fotura.processors.before_each_processors.video_timestamp_extract_before_each_processor import (
    VideoTimestampExtractBeforeEachProcessor,
)

BEFORE_EACH_PROCESSOR_MAP = {
    "filename_timestamp_extract": FilenameTimestampExtractBeforeEachProcessor,
    "video_timestamp_extract": VideoTimestampExtractBeforeEachProcessor,
}

AFTER_EACH_PROCESSOR_MAP = {}

AFTER_ALL_PROCESSOR_MAP = {"google_photos_upload": GooglePhotosUploadAfterAllProcessor}

ALL_PROCESSOR_MAP = {
    **BEFORE_EACH_PROCESSOR_MAP,
    **AFTER_EACH_PROCESSOR_MAP,
    **AFTER_ALL_PROCESSOR_MAP,
}
