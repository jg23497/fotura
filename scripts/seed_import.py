#!/usr/bin/env python3
"""Prepare temporary directories for end-to-end testing of Fotura.

Creates an input directory populated with test images and an empty output
directory, then prompts before cleaning up both directories.

Usage: uv run scripts/seed_import.py
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

TEST_DATA_DIRECTORY = Path(__file__).resolve().parent.parent / "tests" / "data"


def main() -> None:
    if not TEST_DATA_DIRECTORY.exists():
        raise SystemExit(f"Test data directory not found: {TEST_DATA_DIRECTORY}")

    input_directory, output_directory, run_directory = __create_directories()
    __seed_input(input_directory)
    __print_instructions(input_directory, output_directory)

    try:
        input("Press Enter to clean up both directories...")
    finally:
        __cleanup(run_directory)


def __create_directories() -> tuple[Path, Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_directory = Path(tempfile.gettempdir()) / "fotura" / "tests" / timestamp

    input_directory = run_directory / "input"
    output_directory = run_directory / "output"

    input_directory.mkdir(parents=True)
    output_directory.mkdir()

    return input_directory, output_directory, run_directory


def __seed_input(input_directory: Path) -> None:
    shutil.copytree(TEST_DATA_DIRECTORY, input_directory, dirs_exist_ok=True)


def __print_instructions(input_directory: Path, output_directory: Path) -> None:
    file_count = sum(1 for f in input_directory.rglob("*") if f.is_file())

    print(f"Input:  {input_directory}  ({file_count} files)")
    print(f"Output: {output_directory}")
    print()
    print("Suggested command:")
    print()
    print(
        f'  uv run fotura import "{input_directory}" "{output_directory}"'
        " --before-each filename_timestamp_extract"
    )
    print()


def __cleanup(run_directory: Path) -> None:
    shutil.rmtree(run_directory, ignore_errors=True)
    print("Cleaned up.")


if __name__ == "__main__":
    main()
