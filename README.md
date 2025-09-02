# PhotoTidy

<img src="./docs/images/logo.jpg" width="400px" alt="PhotoTidy logo"/>

[![Python CI](https://github.com/jg23497/phototidy/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/jg23497/phototidy/actions/workflows/main.yml)

A command-line tool for organizing and sorting photos based on their metadata and EXIF data. PhotoTidy automatically organizes photos into a structured directory hierarchy by year and month, and can extract date information from various sources including EXIF metadata, and WhatsApp and Android photo filenames. It also provides an extensible pre and post-processor system for plugging in new functionality, like automated Google Photos uploads.

## Features

- **Automatic photo organization**: Sorts photos into a year/month directory structure.
- **Multiple date extraction methods**: 
  - EXIF metadata extraction
  - WhatsApp photo filename parsing
  - Android photo filename parsing
- **Pre-processor and post-processor system**: Extensible framework for plugging in photo additional processing functionality.
- **Dry-run mode**: Preview changes without actually moving files.
- **Comprehensive reporting**: HTML report of all operations performed.
- **Conflict resolution**: Automatically handles filename conflicts.

## Supported File Formats

PhotoTidy supports the following image formats:
- JPEG (.jpg, .jpeg)
- TIFF (.tiff, .tif)

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

### Installing PhotoTidy

After installing uv, install the project dependencies:

```bash
uv pip install .
```

## Usage

### Basic Usage

```bash
phototidy /path/to/photos /path/to/organized/photos
```

### Command Line Options

```bash
phototidy [OPTIONS] DIRECTORY TARGET_ROOT
```

**Arguments:**
- `DIRECTORY`: Source directory containing photos to organize
- `TARGET_ROOT`: Target directory where organized photos will be stored

**Options:**
- `--dry-run`: Show what would be done without making changes
- `--preprocessors TEXT`: Comma-separated list of preprocessors to enable
- `--postprocessors TEXT`: Comma-separated list of postprocessors to enable

### Examples

**Basic photo organization:**
```bash
phototidy ~/Pictures/unsorted ~/Pictures/organized
```

**Dry-run to preview changes:**
```bash
phototidy ~/Pictures/unsorted ~/Pictures/organized --dry-run
```

#### Processors

You can specify multiple pre and post-processors like: `--preprocessors "foo" --preprocessors "bar"` to use the `foo` and `bar` processors:

**Enable FilenameTimestampExtract pre-processor:**
```bash
phototidy --preprocessors "filename_timestamp_extract" ~/Pictures/unsorted ~/Pictures/organized
```

**Enable the Google Photos Upload post-processor:**

```bash
phototidy --preprocessors "filename_timestamp_extract" --postprocessors "google_photos_upload" ~/Pictures/unsorted ~/Pictures/organized
```

## How It Works

1. **Photo Discovery**: Recursively finds all image files in the source directory.
2. **Pre-processor execution**: Executes all specified pre-processors.
3. **Date Extraction**: Attempts to extract date information using EXIF metadata.
4. **Organization**: Creates year/month directory structure and moves files.
5. **Conflict Resolution**: Automatically handles filename conflicts by appending numbers.
6. **Post-processor execution**: Executes all specified post-processors.
7. **Reporting**: Generates an HTML report of all operations.

## Directory Structure

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

## Pre-processors

- **FilenameTimestampExtract Preprocessor**: Extract image timestamp data from WhatsApp or Android photos and updates EXIF metadata (`--preprocessors "filename_timestamp_extract"`)

## Post-processors

- **[Google Photos Upload Processor](./docs/postprocessors/google_photos_upload_postprocessor/google_photos_upload_postprocessor.md)**: Uploads photos to the Google Photos API (`--postprocessors "google_photos_upload"`).

## Development

### Running PhotoTidy in development

In development, access the main entrypoint like so:

```bash
uv run src/photo_tidy/main.py
```

Alternatively, install the package in editable mode:

```bash
uv pip install -e .
```

This will make the `phototidy` command available for testing during development.

For unix-like systems, use the Makefile (e.g. `make test`, `make ci`).

### Running Tests

To run the test suite:

```bash
uv run pytest
```
