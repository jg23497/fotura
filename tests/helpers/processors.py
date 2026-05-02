from unittest.mock import Mock

from fotura.processors.context import Context


class DummyBeforeEachProcessor:
    def __init__(
        self,
        context: Context,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock(return_value={})


class ComplexDummyBeforeEachProcessor:
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


class DummyAfterEachProcessor:
    def __init__(
        self,
        context: Context,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.can_handle: Mock = Mock(return_value=True)
        self.process: Mock = Mock(return_value={})


class ComplexDummyAfterEachProcessor:
    def __init__(
        self,
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


class FailingConfigureBeforeEachProcessor:
    def __init__(self, context: Context) -> None:
        self.context = context

    def configure(self):
        raise RuntimeError("configuration failed")


class ComplexDummyAfterAllProcessor:
    def __init__(
        self,
        context: Context,
        concurrency: int = 2,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.process: Mock = Mock(return_value=None)
        self.concurrency = concurrency


class DummyAfterAllProcessor:
    def __init__(
        self,
        context: Context,
    ) -> None:
        self.context = context
        self.configure = Mock()
        self.process: Mock = Mock(return_value=None)


class ResumableDummyAfterAllProcessor:
    def __init__(self, context: Context) -> None:
        self.context = context

    def configure(self) -> None:
        pass

    def process(self, _photos) -> None:
        return None

    def get_retryable(self):
        return iter([])

    def resume(self) -> None:
        pass
