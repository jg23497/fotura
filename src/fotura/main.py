#!/usr/bin/env python3

import inspect
import logging
from pathlib import Path
from typing import Any, Dict, Tuple, Type

import click

from fotura.importer import Importer
from fotura.importing.conflict_resolution.registry import STRATEGIES
from fotura.io.path_format import PathFormat
from fotura.processors.registry import (
    AFTER_ALL_PROCESSOR_MAP,
    AFTER_EACH_PROCESSOR_MAP,
    BEFORE_EACH_PROCESSOR_MAP,
)
from fotura.reporting.logging_config import setup_logging

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def __build_processor_help(processor_map: Dict[str, Type], processor_type: str) -> str:
    """
    Generate a help string listing all available processors and their parameters.

    Args:
        processor_map: Mapping of processor names to processor classes.
        processor_type: Type of processor for help text (e.g., "before-each", "after-each").

    Returns:
        Formatted help text describing each processor and its parameters.
    """
    lines = [
        f"Add a {processor_type} processor with optional parameters.",
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


def run_import(
    directory: Path,
    target_root: Path,
    dry_run: bool,
    open_report: bool,
    before_each_processors: Tuple[str, ...],
    after_each_processors: Tuple[str, ...],
    after_all_processors: Tuple[str, ...],
    conflict_strategy: str,
    target_path_format: str,
) -> None:
    """
    Execute the import operation.

    Imports photos from a source directory into a target directory hierarchy,
    optionally applying processors to the photos.

    Args:
        directory: Source directory containing photos.
        target_root: Target root directory for organized photos.
        dry_run: If True, no actual file operations are performed.
        open_report: If True, opens the generated HTML report.
        before_each_processors: Before-each processor specifications in the form
            "name" or "name:param=value,...".
        after_each_processors: After-each processor specifications in the form
            "name" or "name:param=value,...".
        after_all_processors: After-all processor specifications in the form
            "name" or "name:param=value,...".
        conflict_strategy: Strategy for resolving filename conflicts in the
            target directory.
        target_path_format: Format for the directory structure (using Python's
            date format codes)
    """
    if not PathFormat.is_valid(target_path_format):
        raise click.BadParameter("Target path format is invalid")

    if dry_run:
        logger.warning("Running in dry-run mode - no files will be moved")

    enabled_before_each_processors = []
    if before_each_processors:
        enabled_before_each_processors = [
            __parse_processor_arguments(p.strip(), BEFORE_EACH_PROCESSOR_MAP)
            for p in before_each_processors
        ]

    enabled_after_each_processors = []
    if after_each_processors:
        enabled_after_each_processors = [
            __parse_processor_arguments(p.strip(), AFTER_EACH_PROCESSOR_MAP)
            for p in after_each_processors
        ]

    enabled_after_all_processors = []
    if after_all_processors:
        enabled_after_all_processors = [
            __parse_processor_arguments(p.strip(), AFTER_ALL_PROCESSOR_MAP)
            for p in after_all_processors
        ]

    importer = Importer(
        directory,
        target_root,
        dry_run=dry_run,
        open_report=open_report,
        enabled_before_each_processors=enabled_before_each_processors,
        enabled_after_each_processors=enabled_after_each_processors,
        enabled_after_all_processors=enabled_after_all_processors,
        conflict_resolution_strategy=conflict_strategy,
        target_path_format=target_path_format,
    )
    importer.process_photos()


@click.group()
def cli() -> None:
    pass


@cli.command(name="import")
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
    "--before-each",
    "before_each_processors",
    multiple=True,
    help=__build_processor_help(BEFORE_EACH_PROCESSOR_MAP, "before-each"),
)
@click.option(
    "--after-each",
    "after_each_processors",
    multiple=True,
    help=__build_processor_help(AFTER_EACH_PROCESSOR_MAP, "after-each"),
)
@click.option(
    "--after-all",
    "after_all_processors",
    multiple=True,
    help=__build_processor_help(AFTER_ALL_PROCESSOR_MAP, "after-all"),
)
@click.option(
    "--conflict-strategy",
    type=click.Choice(STRATEGIES.keys(), case_sensitive=False),
    default="keep_both",
    show_default=True,
    help="How to resolve filename conflicts in the target directory",
)
@click.option(
    "--target-path-format",
    default="%Y/%Y-%m",
    show_default=True,
    help="Path format using date format codes (see https://docs.python.org/3/library/datetime.html#format-codes)",
)
def import_cmd(
    directory: Path,
    target_root: Path,
    dry_run: bool,
    open_report: bool,
    before_each_processors: Tuple[str, ...],
    after_each_processors: Tuple[str, ...],
    after_all_processors: Tuple[str, ...],
    conflict_strategy: str,
    target_path_format: str,
) -> None:
    run_import(
        directory=directory,
        target_root=target_root,
        dry_run=dry_run,
        open_report=open_report,
        before_each_processors=before_each_processors,
        after_each_processors=after_each_processors,
        after_all_processors=after_all_processors,
        conflict_strategy=conflict_strategy,
        target_path_format=target_path_format,
    )


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
    cli()
