from unittest.mock import patch

import pytest

from fotura.persistence.database import Database
from fotura.processors.context import Context
from fotura.processors.processor_orchestrator import ProcessorOrchestrator
from fotura.utils.synchronized_counter import SynchronizedCounter
from tests.helpers.processors import ResumableDummyAfterAllProcessor


@pytest.fixture
def context(tmp_path):
    return Context(
        user_config_path=tmp_path,
        tally=SynchronizedCounter(),
        database=Database(),
    )


@pytest.fixture
def photo_directory(tmp_path):
    source = tmp_path / "photos"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"x")
    (source / "b.jpg").write_bytes(b"x")
    return source


# run_on_source — after-all processors


def test_run_on_source_passes_all_directory_photos_to_after_all_processor(
    context, photo_directory
):
    received = []

    class TrackingAfterAllProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def process(self, photos):
            received.extend(photos)
            return None

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": TrackingAfterAllProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_after_all_processors=[("dummy", {})]
        )
        count = orchestrator.run_on_source(photo_directory)

    assert len(received) == 2
    assert count == 2


def test_run_on_source_after_all_single_file_wraps_in_list(context, tmp_path):
    file = tmp_path / "a.jpg"
    file.write_bytes(b"x")

    received = []

    class TrackingAfterAllProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def process(self, photos):
            received.extend(photos)
            return None

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": TrackingAfterAllProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_after_all_processors=[("dummy", {})]
        )
        count = orchestrator.run_on_source(file)

    assert count == 1
    assert received[0].path == file


# run_on_source — per-photo processors


def test_run_on_source_before_each_counts_handled_photos(context, photo_directory):
    class AcceptingBeforeEachProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def can_handle(self, photo):
            return True

        def process(self, photo):
            return None

    with patch.dict(
        "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
        {"dummy": AcceptingBeforeEachProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_before_each_processors=[("dummy", {})]
        )
        count = orchestrator.run_on_source(photo_directory)

    assert count == 2


def test_run_on_source_before_each_skips_unhandled_photos(context, photo_directory):
    class RejectingBeforeEachProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def can_handle(self, photo):
            return False

        def process(self, photo):
            return None

    with patch.dict(
        "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
        {"dummy": RejectingBeforeEachProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_before_each_processors=[("dummy", {})]
        )
        count = orchestrator.run_on_source(photo_directory)

    assert count == 0


def test_run_on_source_before_each_single_file(context, tmp_path):
    file = tmp_path / "a.jpg"
    file.write_bytes(b"x")

    received = []

    class TrackingBeforeEachProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def can_handle(self, photo):
            return True

        def process(self, photo):
            received.append(photo)
            return None

    with patch.dict(
        "fotura.processors.registry.BEFORE_EACH_PROCESSOR_MAP",
        {"dummy": TrackingBeforeEachProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_before_each_processors=[("dummy", {})]
        )
        count = orchestrator.run_on_source(file)

    assert count == 1
    assert received[0].path == file


# resume


def test_resume_calls_resume_on_all_resumable_processors(context):
    resume_calls: list = []

    class TrackingResumableProcessor(ResumableDummyAfterAllProcessor):
        def resume(self):
            resume_calls.append(True)

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": TrackingResumableProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context,
            enabled_after_all_processors=[("dummy", {}), ("dummy", {})],
        )

    orchestrator.resume()

    assert len(resume_calls) == 2


def test_resume_raises_when_processor_not_resumable(context):
    class NonResumableProcessor:
        def __init__(self, context):
            self.context = context

        def configure(self):
            pass

        def process(self, photos):
            return None

    with patch.dict(
        "fotura.processors.registry.AFTER_ALL_PROCESSOR_MAP",
        {"dummy": NonResumableProcessor},
    ):
        orchestrator = ProcessorOrchestrator(
            context, enabled_after_all_processors=[("dummy", {})]
        )

    with pytest.raises(ValueError, match="does not support resuming"):
        orchestrator.resume()


def test_resume_raises_when_no_processors_configured(context):
    orchestrator = ProcessorOrchestrator(context)

    with pytest.raises(ValueError, match="does not support resuming"):
        orchestrator.resume()
