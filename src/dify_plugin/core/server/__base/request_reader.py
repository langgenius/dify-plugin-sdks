import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dify_plugin.core.entities.plugin.io import PluginInStream

from dify_plugin.core.server.__base.filter_reader import (
    FilterReader,
)

logger = logging.getLogger(__name__)


class RequestReader(ABC):
    def __init__(self) -> None:
        # Convert class variables to instance variables to avoid global lock contention
        self.lock = threading.Lock()
        self.readers: list[FilterReader] = []

    @abstractmethod
    def _read_stream(self) -> Generator["PluginInStream", None, None]:
        """
        Read stream from stdin
        """
        raise NotImplementedError

    def event_loop(self) -> None:
        # read line by line
        while True:
            try:
                for line in self._read_stream():
                    self._process_line(line)
            except Exception:
                logger.exception("Error in event loop")
                time.sleep(0.01)  # Prevent high CPU usage after failures

    def _process_line(self, data: "PluginInStream") -> None:
        session_id = data.session_id
        self.lock.acquire()
        try:
            readers_to_process = self.readers.copy()
        except Exception as e:
            data.writer.error(
                session_id=session_id,
                data={
                    "error": f"Failed to process request ({type(e).__name__}): {e!s}"
                },
            )
            return
        finally:
            self.lock.release()

        matched_readers = []
        for reader in readers_to_process:
            try:
                result = reader.filter(data)
                if result:
                    matched_readers.append(reader)
            except Exception:
                logger.exception("Error in filter")

        for reader in matched_readers:
            try:
                reader.write(data)
            except Exception:
                logger.exception("Error writing to reader")

    def read(self, filter: Callable[["PluginInStream"], bool]) -> FilterReader:  # noqa: A002
        def close(reader: FilterReader) -> None:
            self.lock.acquire()
            try:
                if reader in self.readers:
                    self.readers.remove(reader)
            finally:
                self.lock.release()

        reader = FilterReader(filter, close_callback=lambda: close(reader))

        self.lock.acquire()
        try:
            self.readers.append(reader)
        finally:
            self.lock.release()

        return reader

    def close(self) -> None:
        """
        close stdin processing
        """
        self.lock.acquire()
        try:
            readers_to_close = self.readers.copy()
            self.readers.clear()
        finally:
            self.lock.release()

        # Close readers outside the lock
        for reader in readers_to_close:
            try:
                reader.close()
            except Exception:
                logger.exception("Error closing reader")
