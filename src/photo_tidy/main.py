#!/usr/bin/env python3

import inspect
import click
from pathlib import Path
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.sorter import PhotoSorter


def __get_processor_params(cls):
    sig = inspect.signature(cls.__init__)
    params = {}
    for name, p in sig.parameters.items():
        if name in ("self", "report", "dry_run"):
            continue
        annotation = p.annotation if p.annotation != inspect._empty else str
        params[name] = annotation
    return params


def __build_preprocessor_help(map):
    lines = [
        "Add a processor with optional parameters.",
        "Format: name or name:option=value",
        "",
        "Available processors:",
    ]
    for name, cls in map.items():
        params = __get_processor_params(cls)
        if params:
            param_str = ", ".join(f"{p}({t.__name__})" for p, t in params.items())
        else:
            param_str = "no parameters"
        lines.append(f"\n- {name}: {param_str}")
    return "\n".join(lines)


@click.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.argument("target_root", type=click.Path(path_type=Path))
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.option(
    "--preprocessors",
    multiple=True,
    help=__build_preprocessor_help(PREPROCESSOR_MAP),
)
@click.option(
    "--postprocessors",
    multiple=True,
    help=__build_preprocessor_help(POSTPROCESSOR_MAP),
)
def main(
    directory: Path,
    target_root: Path,
    dry_run: bool,
    preprocessors: str,
    postprocessors: str,
):
    """Sort photos from a directory into a target root directory."""
    click.echo(f"Processing photos from: {directory}")
    click.echo(f"Target root directory: {target_root}")
    if dry_run:
        click.echo("Running in dry-run mode - no files will be moved")

    enabled_preprocessors = []
    if preprocessors:
        enabled_preprocessors = [
            __parse_processor_arguments(p.strip(), PREPROCESSOR_MAP)
            for p in preprocessors
        ]

    enabled_postprocessors = []
    if postprocessors:
        enabled_postprocessors = [
            __parse_processor_arguments(p.strip(), POSTPROCESSOR_MAP)
            for p in postprocessors
        ]

    sorter = PhotoSorter(
        directory,
        target_root,
        dry_run=dry_run,
        enabled_preprocessors=enabled_preprocessors,
        enabled_postprocessors=enabled_postprocessors,
    )
    sorter.process_photos()


def __cast_arg(value, cls):
    if cls is bool:
        val = value.strip().lower()
        if val == "false":
            return False
        elif val == "true":
            return True
    if isinstance(value, cls):
        return value
    try:
        return cls(value)
    except Exception as e:
        raise ValueError(f"Cannot cast {value!r} to {cls}: {e}")


def __parse_processor_arguments(input, processor_map):
    arguments = dict()

    parts = input.split(":")
    processor_name = parts[0]
    options = parts[1:]

    processor_class = processor_map[processor_name]
    allowed_params = __get_processor_params(processor_class)

    for argument in options:
        param, arg = argument.split("=")
        param_class = allowed_params[param]
        casted_arg = __cast_arg(arg, param_class)
        arguments[param] = casted_arg

    result = (processor_name, arguments)
    return result


if __name__ == "__main__":
    main()
