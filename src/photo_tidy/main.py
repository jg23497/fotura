#!/usr/bin/env python3

import inspect
import click
from pathlib import Path
from typing import Any, Dict, Tuple, Type
from photo_tidy.conflict_resolution.registry import STRATEGIES
from photo_tidy.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP
from photo_tidy.tidy import Tidy


def __get_processor_params(klass: Type) -> Dict[str, Type]:
    """
    Inspect a processor class and return a dictionary of its constructor parameters
    (excluding internal ones like 'self', 'report', etc.).

    Args:
        klass: Processor class to inspect.

    Returns:
        Mapping of parameter names to their annotated types.
    """
    sig = inspect.signature(klass.__init__)
    params: Dict[str, Type] = {}
    for name, p in sig.parameters.items():
        if name in ("self", "context", "report", "dry_run"):
            continue
        annotation = p.annotation if p.annotation != inspect._empty else str
        params[name] = annotation
    return params


def __build_processor_help(processor_map: Dict[str, Type]) -> str:
    """
    Generate a help string listing all available processors and their parameters.

    Args:
        processor_map: Mapping of processor names to processor classes.

    Returns:
        Formatted help text describing each processor and its parameters.
    """
    lines = [
        "Add a processor with optional parameters. Pre-processors execute before file moves",
        "and post-processors execute afterwards.",
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
    help=__build_processor_help(PREPROCESSOR_MAP),
)
@click.option(
    "--postprocessors",
    multiple=True,
    help=__build_processor_help(POSTPROCESSOR_MAP),
)
@click.option(
    "--conflict-strategy",
    type=click.Choice(STRATEGIES.keys(), case_sensitive=False),
    default="keep_both",
    show_default=True,
    help="How to resolve filename conflicts in the target directory",
)
def main(
    directory: Path,
    target_root: Path,
    dry_run: bool,
    open_report: bool,
    preprocessors: Tuple[str, ...],
    postprocessors: Tuple[str, ...],
    conflict_strategy: str,
) -> None:
    """
    Entry point for the CLI.

    Organizes photos from a source directory into a target directory,
    optionally applying pre and post-processors, controlling side effects
    with dry-run, opening a report on completion, and selecting a
    conflict-resolution strategy for target filename collisions.

    Args:
        directory: Source directory containing photos.
        target_root: Target root directory for organized photos.
        dry_run: If True, no actual file operations are performed.
        open_report: If True, opens the generated HTML report.
        preprocessors: Preprocessor specifications in the form
            "name" or "name:param=value,...".
        postprocessors: Postprocessor specifications in the form
            "name" or "name:param=value,...".
        conflict_strategy: Strategy for resolving filename conflicts in the
            target directory.
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
        conflict_resolution_strategy=conflict_strategy,
    )
    tidy.process_photos()


def __cast_arg(value: str, klass: Type) -> Any:
    """
    Convert a string value to the given type, with special handling for booleans.

    Args:
        value: The value to cast.
        klass: Target type to cast to.

    Returns:
        Value cast to the requested type.

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
        input: Processor specification string.
        processor_map: Mapping of processor names to processor classes.

    Returns:
        Processor name and dictionary of parsed arguments.
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
