#!/usr/bin/env python3

import click
from pathlib import Path
from photo_tidy.sorter import PhotoSorter


@click.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.argument("target_root", type=click.Path(path_type=Path))
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.option(
    "--preprocessors",
    help=f"Comma-separated list of preprocessors to enable. Available: {', '.join(PhotoSorter.get_available_preprocessors())}",
)
def main(directory: Path, target_root: Path, dry_run: bool, preprocessors: str):
    """Sort photos from a directory into a target root directory."""
    click.echo(f"Processing photos from: {directory}")
    click.echo(f"Target root directory: {target_root}")
    if dry_run:
        click.echo("Running in dry-run mode - no files will be moved")

    enabled_preprocessors = []
    if preprocessors:
        enabled_preprocessors = [p.strip() for p in preprocessors.split(",")]
        click.echo(f"Enabled preprocessors: {', '.join(enabled_preprocessors)}")

    sorter = PhotoSorter(
        directory,
        target_root,
        dry_run=dry_run,
        enabled_preprocessors=enabled_preprocessors,
    )
    sorter.process_photos()


if __name__ == "__main__":
    main()
