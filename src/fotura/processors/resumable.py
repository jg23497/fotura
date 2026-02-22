from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class Resumable(Protocol):
    def get_retryable(self) -> Iterator[Any]: ...
    def resume(self) -> None: ...
