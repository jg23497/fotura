from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from photo_tidy.preprocessors.filename_timestamp_extract_preprocessor import (
    FilenameTimestampExtractPreprocessor,
)

PREPROCESSOR_MAP = {
    "filename_timestamp_extract": FilenameTimestampExtractPreprocessor,
}

POSTPROCESSOR_MAP = {"google_photos_upload": GooglePhotosUploadPostprocessor}
