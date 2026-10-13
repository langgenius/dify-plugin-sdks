# ruff: file-ignore[import-private-name]

import json
from collections.abc import Callable, Generator

from dify_plugin.core.entities.plugin.io import PluginInStream
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.io_server import IOServer


class MemoryRequestReader(RequestReader):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[PluginInStream] = []

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        yield from self.inputs


class RecordingResponseWriter(ResponseWriter):
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.done_count = 0

    def write(self, data: str) -> None:
        self.writes.append(data)

    def done(self) -> None:
        self.done_count += 1

    @property
    def messages(self) -> list[dict]:
        return [json.loads(line) for line in "".join(self.writes).splitlines() if line]


class CallbackIOServer(IOServer):
    handler: Callable[..., None]

    def _execute_request(
        self,
        session_id: str,
        data: dict,
        reader: RequestReader,
        writer: ResponseWriter,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        self.handler(
            session_id,
            data,
            reader,
            writer,
            conversation_id,
            message_id,
            app_id,
            endpoint_id,
            context,
        )
