# PhotoTidy

<img src="./docs/images/logo.jpg" width="400px" alt="PhotoTidy logo"/>

[![Python CI](https://github.com/jg23497/phototidy/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/jg23497/phototidy/actions/workflows/main.yml)

A command-line tool for organizing and sorting photos based on their metadata and EXIF data. PhotoTidy automatically organizes photos into a structured directory hierarchy by year and month, and can extract date information from various sources including WhatsApp filenames and EXIF metadata.

## Features

- **Automatic photo organization**: Sorts photos into year/month directory structure
- **Multiple date extraction methods**: 
  - WhatsApp filename parsing (IMG-YYYYMMDD-WA####.jpg)
  - EXIF metadata extraction
- **Preprocessor system**: Extensible framework for handling different photo sources
- **Dry-run mode**: Preview changes without actually moving files
- **Comprehensive reporting**: HTML report of all operations performed
- **Conflict resolution**: Automatically handles filename conflicts

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

### Examples

**Basic photo organization:**
```bash
phototidy ~/Pictures/unsorted ~/Pictures/organized
```

**Dry-run to preview changes:**
```bash
phototidy --dry-run ~/Pictures/unsorted ~/Pictures/organized
```

**Enable WhatsApp preprocessor:**
```bash
phototidy --preprocessors whatsapp ~/Pictures/unsorted ~/Pictures/organized
```

**Multiple preprocessors:**
```bash
phototidy --preprocessors "whatsapp,other_preprocessor" ~/Pictures/unsorted ~/Pictures/organized
```

## How It Works

1. **Photo Discovery**: Recursively finds all image files (jpg, jpeg, tiff, tif) in the source directory
2. **Date Extraction**: Attempts to extract date information using:
   - Enabled preprocessors (e.g., WhatsApp filename parsing)
   - EXIF metadata (DateTimeOriginal, DateTimeDigitized, DateTime)
3. **Organization**: Creates year/month directory structure and moves files
4. **Conflict Resolution**: Automatically handles filename conflicts by appending numbers
5. **Reporting**: Generates an HTML report of all operations

## Directory Structure

Photos are organized into the following structure:
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

## Preprocessors

### WhatsApp Preprocessor
- **Pattern**: `IMG-YYYYMMDD-WA####.jpg`
- **Function**: Extracts date from WhatsApp image filenames and updates EXIF metadata
- **Usage**: `--preprocessors whatsapp`

## Development

The project structure is organized as follows:
- `src/` - Source code directory
  - `photo_tidy/` - Core functionality
    - `main.py` - Main CLI entry point
    - `sorter.py` - Photo sorting logic
    - `preprocessors/` - Preprocessor implementations
    - `reporting/` - Reporting system
    - `exif_utils.py` - EXIF data extraction utilities

### Development

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
