import inspect
from pathlib import Path
from typing import Any, Dict, List, Type

import click

from fotura.processors.context import Context
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.processors.registry import (
    AFTER_EACH_PROCESSOR_MAP,
    BEFORE_EACH_PROCESSOR_MAP,
)
from fotura.utils.synchronized_counter import SynchronizedCounter

INTERNAL_PARAMETERS = frozenset(("self", "context", "dry_run"))


def get_processor_params(klass: Type) -> Dict[str, inspect.Parameter]:
    sig = inspect.signature(klass.__init__)
    return {
        name: p for name, p in sig.parameters.items() if name not in INTERNAL_PARAMETERS
    }


def build_run_subcommand(
    processor_name: str, proc_cls: Type, user_config_path: Path
) -> click.Command:
    params: List = [
        click.Argument(["source"], type=click.Path(exists=True, path_type=Path)),
        click.Option(
            ["--dry-run"],
            is_flag=True,
            help="Show what would be done without making changes",
        ),
        *__build_processor_options(proc_cls),
    ]

    def callback(**kwargs: Any) -> None:
        source = kwargs.pop("source")
        dry_run = kwargs.pop("dry_run")

        args = {k: v for k, v in kwargs.items() if v is not None}

        orchestrator = __build_orchestrator(
            processor_name, args, dry_run, user_config_path
        )

        count = orchestrator.run_on_source(source)
        click.echo(f"Processed {count} file(s).")

    return click.Command(name=processor_name, callback=callback, params=params)


def build_resume_subcommand(
    processor_name: str, proc_cls: Type, user_config_path: Path
) -> click.Command:
    """Build a Click command that resumes a processor from its last checkpoint."""
    params: List = [
        click.Option(
            ["--dry-run"],
            is_flag=True,
            help="Show what would be done without making changes",
        ),
        *__build_processor_options(proc_cls),
    ]

    def callback(**kwargs: Any) -> None:
        dry_run = kwargs.pop("dry_run")
        args = {k: v for k, v in kwargs.items() if v is not None}

        orchestrator = __build_orchestrator(
            processor_name, args, dry_run, user_config_path
        )

        try:
            orchestrator.resume()
        except ValueError:
            raise click.UsageError(
                f"Processor '{processor_name}' does not support resuming"
            )

    return click.Command(name=processor_name, callback=callback, params=params)


def __build_processor_options(proc_cls: Type) -> List[click.Option]:
    options = []
    for param_name, p in get_processor_params(proc_cls).items():
        annotation = p.annotation if p.annotation != inspect.Parameter.empty else str
        has_default = p.default != inspect.Parameter.empty
        options.append(
            click.Option(
                [f"--{param_name.replace('_', '-')}"],
                type=annotation,
                default=p.default if has_default else None,
                required=not has_default,
                show_default=has_default,
            )
        )

    return options


def __build_orchestrator(
    name: str, args: Dict[str, Any], dry_run: bool, user_config_path: Path
) -> ProcessorOrchestrator:
    context = Context(
        user_config_path=user_config_path,
        tally=SynchronizedCounter(),
        dry_run=dry_run,
    )
    spec = [(name, args)]

    if name in BEFORE_EACH_PROCESSOR_MAP:
        return ProcessorOrchestrator(context, enabled_before_each_processors=spec)
    elif name in AFTER_EACH_PROCESSOR_MAP:
        return ProcessorOrchestrator(context, enabled_after_each_processors=spec)
    else:
        return ProcessorOrchestrator(context, enabled_after_all_processors=spec)
