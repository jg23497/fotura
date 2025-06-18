# PhotoTidy

A command-line tool for organizing and sorting photos.

## Setup

This project uses `uv` for dependency management. To set up the project:

1. Install uv using the standalone installer:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install dependencies:
```bash
uv pip install .
```

## Usage

```bash
uv run src/main.py /path/to/photos
```

## Development

The project structure is organized as follows:
- `src/` - Source code directory
  - `main.py` - Main entry point
  - `photo_tidy/` - Core functionality
    - `__init__.py`
    - `sorter.py` - Photo sorting logic

### Running Tests

To run the test suite:

```bash
uv run pytest
```

This will run all tests with verbose output and coverage reporting. 