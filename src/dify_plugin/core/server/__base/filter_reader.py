import queue
from collections.abc import Callable, Generator
from queue import Queue
from types import TracebackType
from typing import Self, overload

from dify_plugin.core.entities.plugin.io import PluginInStream


class FilterReader:
    filter: Callable[[PluginInStream], bool]
    queue: Queue[PluginInStream | None]
    close_callback: Callable | None

    def __init__(
        self,
        filter: Callable[[PluginInStream], bool],  # noqa: A002
        close_callback: Callable | None = None,
    ) -> None:
        self.filter = filter
        self.queue = Queue()
        self.close_callback = close_callback

    @overload
    def read(
        self, timeout_for_round: float
    ) -> Generator[PluginInStream | None, None, None]: ...

    @overload
    def read(self) -> Generator[PluginInStream, None, None]: ...

    def read(
        self, timeout_for_round: float | None = None
    ) -> Generator[PluginInStream | None, None, None]:
        while True:
            try:
                data = self.queue.get(timeout=timeout_for_round)
                if data is None:
                    break

                yield data
            except queue.Empty:
                yield None
            except Exception:
                break

    def close(self) -> None:
        if self.close_callback:
            self.close_callback()

        self.queue.put(None)

    def write(self, data: PluginInStream) -> None:
        self.queue.put(data)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
