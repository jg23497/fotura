#!/usr/bin/env python3

import click
from pathlib import Path
from photo_tidy.sorter import PhotoTidy


@click.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.argument("target_root", type=click.Path(path_type=Path))
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
def main(directory: Path, target_root: Path, dry_run: bool):
    """Sort photos from a directory into a target root directory."""
    click.echo(f"Processing photos from: {directory}")
    click.echo(f"Target root directory: {target_root}")
    if dry_run:
        click.echo("Running in dry-run mode - no files will be moved")

    sorter = PhotoTidy(directory, target_root, dry_run=dry_run)
    sorter.process_photos()


if __name__ == "__main__":
    main()
