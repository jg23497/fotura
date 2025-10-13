from unittest.mock import Mock

from photo_tidy.processors.context import Context


class DummyPreprocessor:
    def __init__(
        self,
        context: Context,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock(return_value={})


class ComplexDummyPreprocessor:
    def __init__(
        self,
        *,
        context: Context,
        max_size: int,
        should_do_something: bool = True,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock(return_value={})
        self.max_size = max_size
        self.should_do_something = should_do_something


class DummyPostprocessor:
    def __init__(
        self,
        context: Context,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock()


class ComplexDummyPostprocessor:
    def __init__(
        self,
        context: Context,
        max_size: int,
        should_do_something: bool = True,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock()
        self.max_size = max_size
        self.should_do_something = should_do_something
