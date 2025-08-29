from photo_tidy.postprocessors.google_photos_upload_postprocessor import (
    GooglePhotosUploadPostprocessor,
)
from photo_tidy.preprocessors.whatsapp_preprocessor import WhatsAppPreprocessor


PREPROCESSOR_MAP = {"whatsapp": WhatsAppPreprocessor}

POSTPROCESSOR_MAP = {"google_photos_upload": GooglePhotosUploadPostprocessor}
