# Fotura

<img src="./docs/images/logo.jpg" width="400px" alt="Fotura logo"/>

[![Python CI](https://github.com/jg23497/fotura/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/jg23497/fotura/actions/workflows/main.yml)

A command-line tool for organizing and sorting photos based on their metadata. Fotura automatically organizes photos into a structured directory hierarchy based on their timestamps, extracting date information from sources including EXIF metadata and filenames. It also provides an extensible pre and post-processor system for plugging in new functionality, like automated Google Photos uploads.

## Features

- **Automatic photo organization**: Sorts photos into a configurable directory structure (`%Y/%Y-%m` by default, like `2008/2008-05`)
- **Multiple date extraction methods**:
  - EXIF metadata extraction
  - WhatsApp photo filename parsing
  - Android photo filename parsing
- **Pre-processor and post-processor system**: Extensible framework for plugging in photo additional processing functionality, like Google
  Photos uploads.
- **Dry-run mode**: Preview changes without actually moving or modifying any files.
- **Comprehensive reporting**: HTML report of all operations performed.
- **Conflict resolution**: Automatically handles filename conflicts using configurable strategies.

## Supported File Formats

Fotura supports the following image formats:

- JPEG (.jpg, .jpeg)
- TIFF (.tiff, .tif)
- Sony RAW (.arw)

## Setup

This project uses `uv` for dependency management. To set up the project:

### Installing uv

#### MacOS and Linux (Unix-like systems)

Install uv using the standalone installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows

Install uv using one of these methods:

**Option 1: Using PowerShell (recommended)**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Option 2: Using pip**

```cmd
pip install uv
```

**Option 3: Using winget**

```cmd
winget install astral-sh.uv
```

### Installing Fotura

After installing uv, install the project dependencies:

```bash
uv pip install .
```

## Usage

### Basic Usage

```bash
fotura import /path/to/photos /path/to/organized/photos
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
- `--preprocessors`: List of preprocessors to enable
- `--postprocessors`: List of postprocessors to enable
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

You can specify multiple pre and post-processors like: `--preprocessors "foo" --preprocessors "bar"` to use the `foo` and `bar` processors:

**Enable FilenameTimestampExtract pre-processor:**

```bash
fotura import --preprocessors "filename_timestamp_extract" ~/Pictures/unsorted ~/Pictures/organized
```

**Enable the Google Photos Upload post-processor:**

```bash
fotura import --preprocessors "filename_timestamp_extract" --postprocessors "google_photos_upload" ~/Pictures/unsorted ~/Pictures/organized
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

## Pre-processors

- **FilenameTimestampExtract Preprocessor**: Extract image timestamp data from WhatsApp or Android photos and updates EXIF metadata (`--preprocessors "filename_timestamp_extract"`)

## Post-processors

- **[Google Photos Upload Processor](./docs/postprocessors/google_photos_upload_postprocessor/google_photos_upload_postprocessor.md)**: Uploads photos to the Google Photos API (`--postprocessors "google_photos_upload"`).

## Future features

- Concurrent processing.
- Implementing a standalone tool/processor execution mode, like `fotura run google_photos_upload my-image.jpg`.
- Stripping of specific EXIF data (e.g. location data).
- Automatic flagging and skipping of low quality images (i.e. blurry images, under or over-exposed images).
- Image labelling using Llama Vision (multimodal LLM).

## Development

See [Development](docs/development.md).
