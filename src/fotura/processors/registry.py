from fotura.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from fotura.preprocessors.filename_timestamp_extract_preprocessor import (
    FilenameTimestampExtractPreprocessor,
)

PREPROCESSOR_MAP = {
    "filename_timestamp_extract": FilenameTimestampExtractPreprocessor,
}

POSTPROCESSOR_MAP = {"google_photos_upload": GooglePhotosUploadPostprocessor}
