import threading
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from dify_plugin.core.entities.plugin.io import PluginInStream

from dify_plugin.core.server.__base.filter_reader import (
    FilterReader,
)


class RequestReader(ABC):
    lock: threading.Lock = threading.Lock()
    readers: list[FilterReader] = []

    @abstractmethod
    def _read_stream(self) -> Generator["PluginInStream", None, None]:
        """
        Read stream from stdin
        """
        raise NotImplementedError

    def event_loop(self):
        # read line by line
        while True:
            for line in self._read_stream():
                self._process_line(line)

    def _process_line(self, data: "PluginInStream"):
        try:
            session_id = data.session_id
            readers: list[FilterReader] = []
            with self.lock:
                for reader in self.readers:
                    if reader.filter(data):
                        readers.append(reader)

            for reader in readers:
                reader.write(data)
        except Exception as e:
            data.writer.error(
                session_id=session_id,
                data={"error": f"Failed to process request ({type(e).__name__}): {str(e)}"},
            )

    def read(self, filter: Callable[["PluginInStream"], bool]) -> FilterReader:  # noqa: A002
        def close(reader: FilterReader):
            with self.lock:
                self.readers.remove(reader)

        reader = FilterReader(filter, close_callback=lambda: close(reader))

        with self.lock:
            self.readers.append(reader)

        return reader

    def close(self):
        """
        close stdin processing
        """
        for reader in self.readers:
            reader.close()
        self.readers.clear()
