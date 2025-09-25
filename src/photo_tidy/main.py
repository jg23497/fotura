#!/usr/bin/env python3

import inspect
import click
from pathlib import Path
from typing import Any, Dict, Tuple, Type
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.tidy import Tidy


def __get_processor_params(klass: Type) -> Dict[str, Type]:
    """
    Inspect a processor class and return a dictionary of its constructor parameters
    (excluding internal ones like 'self', 'report', etc.).

    Args:
        klass (type): Processor class to inspect.

    Returns:
        dict: Mapping of parameter names to their annotated types.
    """
    sig = inspect.signature(klass.__init__)
    params: Dict[str, Type] = {}
    for name, p in sig.parameters.items():
        if name in ("self", "context", "report", "dry_run"):
            continue
        annotation = p.annotation if p.annotation != inspect._empty else str
        params[name] = annotation
    return params


def __build_preprocessor_help(processor_map: Dict[str, Type]) -> str:
    """
    Generate a help string listing all available processors and their parameters.

    Args:
        processor_map (dict): Mapping of processor names to processor classes.

    Returns:
        str: Formatted help text describing each processor and its parameters.
    """
    lines = [
        "Add a processor with optional parameters.",
        "Format: name or name:option=value",
        "",
        "Available processors:",
    ]
    for name, cls in processor_map.items():
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
    "--open-report",
    is_flag=True,
    help="Open the report in your web browser after completion",
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
    open_report: bool,
    preprocessors: Tuple[str, ...],
    postprocessors: Tuple[str, ...],
) -> None:
    """
    Entry point for the CLI.

    Moves or copies photos from a source directory to a target directory,
    optionally applying pre and post-processors.

    Args:
        directory (Path): Source directory containing photos.
        target_root (Path): Target root directory for organized photos.
        dry_run (bool): If True, no actual file operations are performed.
        preprocessors (list[str]): List of preprocessor specifications.
        postprocessors (list[str]): List of postprocessor specifications.
    """
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

    tidy = Tidy(
        directory,
        target_root,
        dry_run=dry_run,
        open_report=open_report,
        enabled_preprocessors=enabled_preprocessors,
        enabled_postprocessors=enabled_postprocessors,
    )
    tidy.process_photos()


def __cast_arg(value: str, klass: Type) -> Any:
    """
    Convert a string value to the given type, with special handling for booleans.

    Args:
        value (str): The value to cast.
        klass (type): Target type to cast to.

    Returns:
        Any: Value cast to the requested type.

    Raises:
        ValueError: If the value cannot be cast to the target type.
    """
    if klass is bool:
        val = value.strip().lower()
        if val == "false":
            return False
        elif val == "true":
            return True
    if isinstance(value, klass):
        return value
    try:
        return klass(value)
    except Exception as e:
        raise ValueError(f"Cannot cast {value!r} to {klass}: {e}")


def __parse_processor_arguments(
    input: str, processor_map: Dict[str, Type]
) -> Tuple[str, Dict[str, Any]]:
    """
    Parse a processor specification string into a name and argument dictionary.

    Format: "processor_name:param1=value1,param2=value2"

    Args:
        input (str): Processor specification string.
        processor_map (dict): Mapping of processor names to processor classes.

    Returns:
        tuple[str, dict]: Processor name and dictionary of parsed arguments.
    """
    arguments = dict()

    parts = input.split(":")
    processor_name = parts[0]
    options_string = parts[1] if len(parts) > 1 else None

    processor_class = processor_map[processor_name]
    allowed_params = __get_processor_params(processor_class)

    if options_string:
        options = [opt.strip() for opt in options_string.split(",")]
        for argument in options:
            param, arg = argument.split("=")
            param_class = allowed_params[param]
            casted_arg = __cast_arg(arg, param_class)
            arguments[param] = casted_arg

    return processor_name, arguments


if __name__ == "__main__":
    main()
