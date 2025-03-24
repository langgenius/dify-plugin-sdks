import queue
from collections.abc import Callable, Generator
from queue import Queue
from typing import Optional, overload

from dify_plugin.core.entities.plugin.io import PluginInStream


class FilterReader:
    filter: Callable[[PluginInStream], bool]
    queue: Queue[PluginInStream | None]
    close_callback: Optional[Callable]

    def __init__(
        self,
        filter: Callable[[PluginInStream], bool],  # noqa: A002
        close_callback: Optional[Callable] = None,
    ) -> None:
        self.filter = filter
        self.queue = Queue()
        self.close_callback = close_callback

    @overload
    def read(self, timeout_for_round: float) -> Generator[PluginInStream | None, None, None]: ...

    @overload
    def read(self) -> Generator[PluginInStream, None, None]: ...

    def read(self, timeout_for_round: Optional[float] = None) -> Generator[PluginInStream | None, None, None]:
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

    def close(self):
        if self.close_callback:
            self.close_callback()

        self.queue.put(None)

    def write(self, data: PluginInStream):
        self.queue.put(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
