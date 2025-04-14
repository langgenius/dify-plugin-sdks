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
    def __init__(self):
        # Convert class variables to instance variables to avoid global lock contention
        self.lock = threading.Lock()
        self.readers = []

    @abstractmethod
    def _read_stream(self) -> Generator["PluginInStream", None, None]:
        """
        Read stream from stdin
        """
        raise NotImplementedError

    def event_loop(self):
        # read line by line
        while True:
            try:
                for line in self._read_stream():
                    self._process_line(line)
            except Exception:
                logger.exception("Error in event loop")
                time.sleep(0.01)  # Prevent high CPU usage

    def _process_line(self, data: "PluginInStream"):
        try:
            session_id = data.session_id
            readers_to_process = []

            # Acquire lock to safely access readers list
            self.lock.acquire()
            try:
                # Safely copy the reader list under lock protection
                readers_to_process = self.readers.copy()
            finally:
                self.lock.release()

            # Execute filter operations outside of lock
            matched_readers = []
            for reader in readers_to_process:
                try:
                    result = reader.filter(data)
                    if result:
                        matched_readers.append(reader)
                except Exception:
                    logger.exception("Error in filter")

            # Process readers in batches to avoid blocking
            for reader in matched_readers:
                try:
                    reader.write(data)
                except Exception:
                    logger.exception("Error writing to reader")

        except Exception as e:
            data.writer.error(
                session_id=session_id,
                data={"error": f"Failed to process request ({type(e).__name__}): {e!s}"},
            )

    def read(self, filter: Callable[["PluginInStream"], bool]) -> FilterReader:  # noqa: A002
        def close(reader: FilterReader):
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

    def close(self):
        """
        close stdin processing
        """
        readers_to_close = []

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
