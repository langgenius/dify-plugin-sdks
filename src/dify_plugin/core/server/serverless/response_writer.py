from collections.abc import Callable
from contextvars import copy_context
from queue import Empty, Queue
from threading import Lock

from gevent import Greenlet

from dify_plugin.core.server.__base.response_writer import ResponseWriter


class ServerlessResponseWriter(ResponseWriter):
    """
    Writer for a single plugin request
    """

    def __init__(self, queue: Queue) -> None:
        self.q = queue
        self.closed = False
        self._lock = Lock()
        self._task: Greenlet | None = None

    def execute(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if self.closed:
                return
            task = self._task = Greenlet.spawn(copy_context().run, callback)
        try:
            task.get()
        finally:
            with self._lock:
                self._task = None
            task.kill(block=False)

    def write(self, data: bytes) -> None:
        with self._lock:
            if not self.closed:
                self.q.put(data)

    def done(self) -> None:
        with self._lock:
            if not self.closed:
                self.closed = True
                self.q.put(None)

    def close(self) -> None:
        with self._lock:
            self.closed = True
            task = self._task
            while True:
                try:
                    self.q.get_nowait()
                except Empty:
                    break
        if task is not None:
            task.kill(block=False)
