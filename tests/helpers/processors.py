from unittest.mock import Mock

from photo_tidy.reporting.report import Report


class DummyPreprocessor:
    def __init__(
        self,
        *,
        dry_run: bool = False,
        can_handle: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.can_handle: Mock = Mock(return_value=can_handle)
        self.process: Mock = Mock(return_value={})


class ComplexDummyPreprocessor:
    def __init__(
        self,
        *,
        dry_run: bool = False,
        can_handle: bool = True,
        max_size: int,
        should_do_something: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.can_handle: Mock = Mock(return_value=can_handle)
        self.process: Mock = Mock(return_value={})
        self.max_size = max_size
        self.should_do_something = should_do_something


class DummyPostprocessor:
    def __init__(
        self,
        report: Report,
        *,
        dry_run: bool = False,
    ) -> None:
        self.report = report
        self.dry_run = dry_run
        self.set_up = Mock()
        self.process: Mock = Mock()


class ComplexDummyPostprocessor:
    def __init__(
        self,
        report: Report,
        *,
        dry_run: bool = False,
        max_size: int,
        should_do_something: bool = True,
    ) -> None:
        self.report = report
        self.dry_run = dry_run
        self.set_up = Mock()
        self.process: Mock = Mock()
        self.max_size = max_size
        self.should_do_something = should_do_something
