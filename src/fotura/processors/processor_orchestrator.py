import logging
import sys
from typing import Any, Dict, List, Optional, Tuple

from fotura.domain.photo import Photo
from fotura.processors.context import Context
from fotura.processors.registry import (
    AFTER_ALL_PROCESSOR_MAP,
    AFTER_EACH_PROCESSOR_MAP,
    BEFORE_EACH_PROCESSOR_MAP,
)

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
