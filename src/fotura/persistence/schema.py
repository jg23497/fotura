GOOGLE_PHOTOS_UPLOADS = """
CREATE TABLE IF NOT EXISTS google_photos_uploads (
    file_hash TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'uploading', 'failed', 'uploaded')),
    uploaded_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

ALL_TABLES = [
    GOOGLE_PHOTOS_UPLOADS,
]
