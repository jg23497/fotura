import logging
import sys
from typing import Any, Dict, List, Optional, Tuple

from fotura.domain.photo import Photo
from fotura.processors.context import Context
from fotura.processors.registry import POSTPROCESSOR_MAP, PREPROCESSOR_MAP

logger = logging.getLogger(__name__)


class ProcessorOrchestrator:
    def __init__(
        self,
        processor_context: Context,
        enabled_preprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        enabled_postprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ):
        self.processor_context = processor_context
        self.preprocessors = []
        self.postprocessors = []

        self.configure_processors(enabled_preprocessors, enabled_postprocessors)

    def configure_processors(
        self,
        enabled_preprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        enabled_postprocessors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        if enabled_preprocessors:
            self.__configure_processors_list(
                PREPROCESSOR_MAP, enabled_preprocessors, self.preprocessors
            )
        if enabled_postprocessors:
            self.__configure_processors_list(
                POSTPROCESSOR_MAP, enabled_postprocessors, self.postprocessors
            )

    def run_preprocessors(self, photo: Photo) -> None:
        for preprocessor in self.preprocessors:
            if preprocessor.can_handle(photo):
                result = preprocessor.process(photo)
                if result:
                    photo.facts.update(result)

    def run_postprocessors(
        self,
        photo: Photo,
    ):
        for postprocessor in self.postprocessors:
            if not postprocessor.can_handle(photo):
                photo.log(
                    logging.WARNING,
                    "%s cannot handle file",
                    postprocessor.__class__.__name__,
                )
                continue
            result = postprocessor.process(photo)
            if result:
                photo.facts.update(result)

    def __configure_processors_list(
        self, processor_map, enabled_processors, processor_instances
    ) -> None:
        for processor_name, processor_args in enabled_processors:
            if processor_name in processor_map:
                instance = processor_map[processor_name](
                    context=self.processor_context, **processor_args
                )
                instance.configure()
                processor_instances.append(instance)
            else:
                logger.error(f"Unknown processor: {processor_name}")
                sys.exit(1)
