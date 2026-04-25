from queue import Queue

from dify_plugin.core.server.__base.response_writer import ResponseWriter


class ServerlessResponseWriter(ResponseWriter):
    """
    Writer for a single plugin request
    """

    def __init__(self, queue: Queue) -> None:
        self.q = queue

    def write(self, data: bytes) -> None:
        self.q.put(data)

    def done(self):
        self.q.put(None)
