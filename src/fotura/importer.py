import errno
import logging
import webbrowser
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
)

from platformdirs import user_config_dir, user_data_dir

from fotura.domain.media_file import MediaFile
from fotura.domain.photo import Photo
from fotura.domain.photo_cluster import PhotoCluster
from fotura.importing.conflict_resolution import registry
from fotura.importing.media_finder import MediaFinder, MediaType
from fotura.importing.photo_clusterer import PhotoClusterer
from fotura.io.files import Files
from fotura.io.path_resolver import PathResolver
from fotura.io.photos.exif.exif_data import ExifData
from fotura.processors.context import Context
from fotura.processors.fact_type import FactType
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.reporting.logging_config import configure_report
from fotura.utils.synchronized_counter import SynchronizedCounter

logger = logging.getLogger(__name__)


class Importer:
    def __init__(
        self,
        input_path: Path,
        target_root: Path,
        dry_run: bool = False,
        enabled_before_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_each_processors: Optional[
            List[Tuple[str, Dict[str, Any]]]
        ] = None,
        enabled_after_all_processors: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
        open_report: bool = False,
        conflict_resolution_strategy: str = "keep_both",
        target_path_format: str = "%Y/%Y-%m",
        concurrency: int = 1,
        media_types: Collection[MediaType] = (MediaType.PHOTOS,),
        cluster_photos: bool = False,
    ):
        self.input_path = input_path
        self.target_root = target_root
        self.dry_run = dry_run
        self.target_path_format = target_path_format
        self.open_report = open_report
        self.concurrency = concurrency
        self.media_types = media_types
        self.cluster_photos = cluster_photos
        self.tally = SynchronizedCounter({"errored": 0})

        self.__configure_dependencies(
            conflict_resolution_strategy,
            enabled_before_each_processors,
            enabled_after_each_processors,
            enabled_after_all_processors,
        )

    def process_media_files(self):
        logger.info(
            "Importing media files from %s to %s (dry-run: %s)",
            self.input_path,
            self.target_root,
            str(self.dry_run).lower(),
        )

        logger.info("Writing report to %s", self.report_path)

        self.files.has_read_write_permissions(self.input_path)

        processed_media_files = []

        try:
            media_files = list(self.media_finder.find())

            prepared_media_files = self.__prepare_with_concurrency(media_files)

            if self.cluster_photos:
                self.__cluster_photos(prepared_media_files)

            self.files.ensure_sufficient_space(prepared_media_files, self.target_root)

            processed_media_files = self.__process_with_concurrency(
                prepared_media_files
            )

            if processed_media_files:
                self.processor_orchestrator.run_after_all_processors(
                    processed_media_files
                )
        finally:
            self.__close_report()

    def __process_with_concurrency(
        self, media_files: Iterable[MediaFile]
    ) -> List[MediaFile]:
        return self.__run_with_concurrency(media_files, self.__process_media_file)

    def __prepare_with_concurrency(
        self, media_files: Iterable[MediaFile]
    ) -> List[MediaFile]:
        return self.__run_with_concurrency(media_files, self.__prepare_media_file)

    def __run_with_concurrency(
        self,
        media_files: Iterable[MediaFile],
        operation: Callable[[MediaFile], bool],
    ) -> List[MediaFile]:
        if self.concurrency == 1:
            return self.__run_sequentially(media_files, operation)

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            return self.__run_windowed(executor, iter(media_files), operation)

    def __run_windowed(
        self,
        executor: ThreadPoolExecutor,
        media_files: Iterator[MediaFile],
        operation: Callable[[MediaFile], bool],
    ) -> List[MediaFile]:
        window_size = self.concurrency * 2
        futures: Dict[Future[bool], MediaFile] = {}
        processed_media_files: List[MediaFile] = []

        for media_file in islice(media_files, window_size):
            futures[executor.submit(operation, media_file)] = media_file

        while futures:
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)

            for future in done:
                media_file = futures.pop(future)

                try:
                    if future.result():
                        processed_media_files.append(media_file)
                except Exception as e:
                    self.__record_error(media_file)
                    if not self.__is_recoverable_error(e, media_file.path):
                        for pending_future in futures:
                            pending_future.cancel()
                        raise

                next_media_file = next(media_files, None)
                if next_media_file is not None:
                    futures[executor.submit(operation, next_media_file)] = (
                        next_media_file
                    )

        return processed_media_files

    def __run_sequentially(
        self,
        media_files: Iterable[MediaFile],
        operation: Callable[[MediaFile], bool],
    ) -> List[MediaFile]:
        processed_media_files = []

        for media_file in media_files:
            try:
                if operation(media_file):
                    processed_media_files.append(media_file)
            except Exception as e:
                self.__record_error(media_file)
                if self.__is_recoverable_error(e, media_file.path):
                    continue
                raise

        return processed_media_files

    def __prepare_media_file(self, media_file: MediaFile) -> bool:
        self.files.ensure_writable(media_file)
        self.processor_orchestrator.run_before_each_processors(media_file)

        if FactType.TAKEN_TIMESTAMP not in media_file.facts and isinstance(
            media_file, Photo
        ):
            timestamp = ExifData.extract_date(media_file)
            if timestamp is not None:
                media_file.facts[FactType.TAKEN_TIMESTAMP] = timestamp

        return True

    def __process_media_file(self, media_file: MediaFile) -> bool:
        target_path = self.path_resolver.get_target_path(media_file)

        if target_path is not None:
            self.files.move(media_file, target_path)
            self.tally.increment("moved")
            self.processor_orchestrator.run_after_each_processors(media_file)
            return True
        else:
            self.tally.increment("skipped")
            return False

    def __cluster_photos(self, media_files: list[MediaFile]) -> None:
        try:
            photo_clusters = self.photo_clusterer.cluster(
                [
                    media_file
                    for media_file in media_files
                    if isinstance(media_file, Photo)
                ]
            )
        except Exception:
            logger.error(
                "Photo clustering failed; continuing without clusters",
                exc_info=True,
            )
            self.html_report_handler.set_photo_clusters([])
            return

        self.html_report_handler.set_photo_clusters(photo_clusters)
        self.__report_photo_clusters(photo_clusters)

    @staticmethod
    def __report_photo_clusters(photo_clusters: list[PhotoCluster]) -> None:
        visual_clusters = [
            cluster for cluster in photo_clusters if len(cluster.photos) > 1
        ]
        clustered_photo_count = sum(len(cluster.photos) for cluster in visual_clusters)
        logger.info(
            "Photo clustering identified %d cluster(s) containing %d photo(s)",
            len(visual_clusters),
            clustered_photo_count,
        )

    def __configure_dependencies(
        self,
        conflict_resolution_strategy,
        enabled_before_each_processors,
        enabled_after_each_processors,
        enabled_after_all_processors,
    ):
        self.user_config_path = Path(user_config_dir("fotura"))
        self.user_data_path = Path(user_data_dir("fotura"))

        self.__setup_report()

        self.conflict_resolver = registry.get_conflict_resolver(
            conflict_resolution_strategy
        )
        self.media_finder = MediaFinder(self.input_path, media_types=self.media_types)
        self.files = Files(self.dry_run)
        self.photo_clusterer = PhotoClusterer(concurrency=self.concurrency)
        self.path_resolver = PathResolver(
            self.target_root,
            self.target_path_format,
            self.conflict_resolver,
            self.dry_run,
        )

        processor_context = Context(
            user_config_path=self.user_config_path,
            dry_run=self.dry_run,
            tally=self.tally,
        )

        self.processor_orchestrator = ProcessorOrchestrator(
            processor_context,
            enabled_before_each_processors,
            enabled_after_each_processors,
            enabled_after_all_processors,
        )

    def __setup_report(self):
        report_dir = self.user_data_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_path = report_dir / f"import-report-{timestamp}.html"

        self.html_report_handler = configure_report(
            self.report_path,
            dry_run=self.dry_run,
        )

    def __close_report(self):
        self.html_report_handler.close(self.tally)
        if self.open_report:
            webbrowser.open(self.report_path.as_uri())

    def __record_error(self, media_file: MediaFile) -> None:
        media_file.log(logging.ERROR, "Failed to import", exc_info=True)
        self.tally.increment("errored")

    @staticmethod
    def __is_recoverable_error(e: Exception, media_file_path: Path) -> bool:
        if isinstance(e, OSError) and e.errno == errno.ENOSPC:
            return False
        filename = getattr(e, "filename", None)
        return bool(filename) and Path(filename) == media_file_path
