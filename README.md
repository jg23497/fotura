# Fotura

<img src="./docs/images/logo.jpg" width="200px" alt="Fotura logo"/>

**A Python CLI application for importing, organizing and uploading (backing up) your photos.**

[![Python CI](https://github.com/jg23497/fotura/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/jg23497/fotura/actions/workflows/main.yml)

## Features

- **Automatic photo organization**: Intelligently imports photos into a hierarchical directory structure based on their taken timestamps (`%Y/%Y-%m` by default, like `2008/2008-05`).
- **Supports multiple timestamp extraction methods**:
  - EXIF metadata extraction
  - WhatsApp and Android filename parsing
- **Google Photos Uploads**: Using the extensible processors framework to upload your photos via the Google Photos API.
- **Dry-run mode**: Fully preview changes without moving or modifying your files.
- **Conflict resolution**: Automatically handle filename conflicts using configurable strategies.

## Installation

```
# Install pipx if not already installed
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install Fotura
pipx install fotura

# Run Fotura
fotura --help
```

> [!TIP]
> **Why pipx?**
> - Configures a "global" command without touching system Python packages.
> - Installs Fotura in an isolated environment, keeping its dependencies separate from those for other Python projects on your system.
> - It's easy to uninstall with `pipx uninstall fotura`.

## Usage

### Basic Usage

```bash
fotura import /photos/to/import /home/user/Pictures
```

### Command Line Options

```bash
fotura import [OPTIONS] DIRECTORY TARGET_ROOT
```

**Arguments:**

- `DIRECTORY`: Source directory containing photos to organize
- `TARGET_ROOT`: Target directory where organized photos will be stored

**Options:**

- `--dry-run`: Show what would be done without making changes
- `--before-each`: List of before-each processors to enable (run for each photo before moving)
- `--after-each`: List of after-each processors to enable (run for each photo after moving)
- `--after-all`: List of after-all processors to enable (run once after all photos are processed)
- `--open-report`: Optionally open the report once processing completes
- `--conflict-strategy`: How to resolve conflicts in the target directory
- `--target-path-format`: Target path format

### Examples

**Basic photo organization:**

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized
```

**Dry run to preview changes:**

Always perform a dry run first to be sure your files are moved as you expect, based on the configuration. Fotura will not modify, move or otherwise touch
your files during a dry run.

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized --dry-run
```

Add `--open-report` to view the report in your web browser:

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized --dry-run --open-report
```

<img src="./docs/images/report-example.png" width="600px" alt="Example report"/>

#### Processors

You can specify multiple before-each and after-each processors like: `--before-each "foo" --before-each "bar"` to use the `foo` and `bar` processors:

**Enable FilenameTimestampExtract before-each processor:**

```bash
fotura import --before-each "filename_timestamp_extract" ~/Pictures/unsorted ~/Pictures/organized
```

**Enable the Google Photos Upload after-each processor:**

```bash
fotura import --before-each "filename_timestamp_extract" --after-each "google_photos_upload" ~/Pictures/unsorted ~/Pictures/organized
```

**Override the default path format:**

By default, photos are organized into the following structure:

```
target_root/
├── 2023/
│   ├── 2023-01/
│   ├── 2023-02/
│   └── ...
├── 2024/
│   ├── 2024-01/
│   ├── 2024-02/
│   └── ...
└── ...
```

You can override this by providing an argument to `target-path-format`, which uses [Python's date string directives](https://docs.python.org/3/library/datetime.html#format-codes).

For example, assuming a target directory root of `~/Pictures/organized` and a photo taken on 2008-05-30, the `"%Y/%Y-%m/%Y-%m-%d"` string will cause the
photo to be moved to `~/Pictures/organized/2008/2008-05/2008-05-30`:

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized --dry-run --open-report --target-path-format="%Y/%Y-%m/%Y-%m-%d"
```

_Note: Always perform a dry run first to ensure your photos will be moved as you would expect._

Other common examples:

| Style                     | Format String                 | Example Path                    |
| ------------------------- | ----------------------------- | ------------------------------- |
| **Year / Month**          | `%Y/%m/example.jpg`           | `2008/05/example.jpg`           |
| **Year / Month (named)**  | `%Y/%B/example.jpg`           | `2008/May/example.jpg`          |
| **Year-Month (flat)**     | `%Y-%m/example.jpg`           | `2008-05/example.jpg`           |
| **Month-Day under year**  | `%Y/%m-%d/example.jpg`        | `2008/05-28/example.jpg`        |
| **Day-Month-Year (flat)** | `%d-%m-%Y/example.jpg`        | `28-05-2008/example.jpg`        |
| **Custom folder name**    | `%Y-%m-%d_photos/example.jpg` | `2008-05-28_photos/example.jpg` |

**Select a conflict strategy:**

The argument to `--conflict-strategy` determines the conflict resolution strategy:

- keep_both: Keep both images, incrementing the conflicting filename (e.g. duplicate.jpg and duplicate_1.jpg will both exist).
- skip: Skip the image to be copied, leaving it in place. No files are deleted.

Example:

```bash
fotura import ~/Pictures/unsorted ~/Pictures/organized --dry-run --open-report --conflict-strategy 'keep_both'
```

## Before-each Processors

- **FilenameTimestampExtract**: Extract image timestamp data from WhatsApp or Android photos and updates EXIF metadata (`--before-each "filename_timestamp_extract"`)

## After-each Processors

- **[Google Photos Upload Processor](./docs/after_each_processors/google_photos_upload_after_each_processor/google_photos_upload_after_each_processor.md)**: Uploads photos to the Google Photos API (`--after-each "google_photos_upload"`).

## After-all Processors

After-all processors run once after all photos have been processed. They receive the complete list of processed photos and can perform batch operations.

- **Google Photos Batch Upload**: Uploads photos to Google Photos using batched API calls (`--after-all "google_photos_upload_batch"`).

  **Parameters:**
  - `concurrency` (int, default: 2): Number of parallel upload threads (1-5)
  - `batch_size` (int, default: 10): Photos per batchCreate API call (1-50)

  **Example:**
  ```bash
  # With default parameters
  fotura import --after-all "google_photos_upload_batch" ~/Pictures/unsorted ~/Pictures/organized
  # With custom parameters
  fotura import --after-all "google_photos_upload_batch:concurrency=3,batch_size=20" ~/Pictures/unsorted ~/Pictures/organized
  ```

  This processor uploads image bytes in parallel using a thread pool, then uses the Google Photos `batchCreate` API to create multiple media items in a single call.

## Future features

- Concurrent processing.
- Implementing a standalone tool/processor execution mode, like `fotura run google_photos_upload my-image.jpg`.
- Stripping of specific EXIF data (e.g. location data).
- Automatic flagging and skipping of low quality images (i.e. blurry images, under or over-exposed images).
- Image labelling using Llama Vision (multimodal LLM).

## Development

See [Development](docs/development.md).
