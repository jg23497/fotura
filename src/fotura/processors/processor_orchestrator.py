import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fotura.domain.photo import Photo
from fotura.importing.media_finder import MediaFinder
from fotura.processors.context import Context
from fotura.processors.registry import (
    AFTER_ALL_PROCESSOR_MAP,
    AFTER_EACH_PROCESSOR_MAP,
    BEFORE_EACH_PROCESSOR_MAP,
)
from fotura.processors.resumable import Resumable

logger = logging.getLogger(__name__)


class ProcessorOrchestrator:
    def __init__(
        self,
        processor_context: Context,
        enabled_before_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_all_processors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ):
        self.processor_context = processor_context
        self.before_each_processors = []
        self.after_each_processors = []
        self.after_all_processors = []

        self.configure_processors(
            enabled_before_each_processors,
            enabled_after_each_processors,
            enabled_after_all_processors,
        )

    def configure_processors(
        self,
        enabled_before_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_all_processors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        if enabled_before_each_processors:
            self.__configure_processors_list(
                BEFORE_EACH_PROCESSOR_MAP,
                enabled_before_each_processors,
                self.before_each_processors,
            )
        if enabled_after_each_processors:
            self.__configure_processors_list(
                AFTER_EACH_PROCESSOR_MAP,
                enabled_after_each_processors,
                self.after_each_processors,
            )
        if enabled_after_all_processors:
            self.__configure_processors_list(
                AFTER_ALL_PROCESSOR_MAP,
                enabled_after_all_processors,
                self.after_all_processors,
            )

    def run_before_each_processors(self, photo: Photo) -> None:
        for processor in self.before_each_processors:
            if processor.can_handle(photo):
                result = processor.process(photo)
                if result:
                    photo.facts.update(result)

    def run_after_each_processors(self, photo: Photo) -> None:
        for processor in self.after_each_processors:
            if not processor.can_handle(photo):
                photo.log(
                    logging.WARNING,
                    "%s cannot handle file",
                    processor.__class__.__name__,
                )
                continue
            result = processor.process(photo)
            if result:
                photo.facts.update(result)

    def run_after_all_processors(self, photos: List[Photo]) -> None:
        for processor in self.after_all_processors:
            result = processor.process(photos)
            if result:
                for photo, facts in result.items():
                    photo.facts.update(facts)

    def run_on_source(self, source: Path) -> int:
        if source.is_dir():
            items = list(MediaFinder(source).find())
        else:
            items = [Photo(source)]

        count = 0

        for processor in self.after_all_processors:
            processor.process(items)

        if self.after_all_processors:
            count = len(items)

        for item in items:
            for processor in self.before_each_processors + self.after_each_processors:
                if processor.can_handle(item):
                    processor.process(item)
                    count += 1

        return count

    def resume(self) -> None:
        all_processors = (
            self.before_each_processors
            + self.after_each_processors
            + self.after_all_processors
        )
        resumed = False
        for processor in all_processors:
            if isinstance(processor, Resumable):
                processor.resume()
                resumed = True

        if not resumed:
            raise ValueError("Processor does not support resuming")

    def __configure_processors_list(
        self, processor_map, enabled_processors, processor_instances
    ) -> None:
        for processor_name, processor_args in enabled_processors:
            try:
                if processor_name in processor_map:
                    instance = processor_map[processor_name](
                        context=self.processor_context, **processor_args
                    )
                    instance.configure()
                    processor_instances.append(instance)
                else:
                    logger.error(f"Unknown processor: {processor_name}")
                    sys.exit(1)
            except Exception:
                logger.error(
                    f"Failed to configure {processor_name} processor", exc_info=True
                )
                sys.exit(1)
