from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.message import SessionMessage
from dify_plugin.core.server.io_server import IOServer
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter


class CapturingResponseWriter(StdioResponseWriter):
    def __init__(self) -> None:
        self.session_messages: list[tuple[str | None, dict]] = []
        self.done_called = False

    def write(self, _data: str) -> None:
        msg = "write should not be called directly"
        raise AssertionError(msg)

    def done(self) -> None:
        self.done_called = True

    def session_message(
        self,
        session_id: str | None = None,
        data: dict | SessionMessage | None = None,
    ) -> None:
        if isinstance(data, SessionMessage):
            data = data.to_dict()
        self.session_messages.append((session_id, data or {}))


class FailingIOServer(IOServer):
    def _execute_request(
        self,
        session_id: str,
        data: dict,
        reader: object,
        writer: object,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        _ = (
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
        msg = "boom"
        raise RuntimeError(msg)


def test_execute_request_error_includes_traceback() -> None:
    reader = StdioRequestReader()
    writer = CapturingResponseWriter()
    server = FailingIOServer(DifyPluginEnv(), reader, writer)

    server._execute_request_in_thread(
        "session-1",
        {},
        reader,
        writer,
    )

    assert writer.done_called
    assert len(writer.session_messages) == 2

    session_id, error_message = writer.session_messages[0]
    assert session_id == "session-1"
    assert error_message["type"] == "error"
    assert error_message["data"]["error_type"] == "RuntimeError"
    assert error_message["data"]["message"] == "boom"
    traceback = error_message["data"]["args"]["traceback"]
    assert "Traceback (most recent call last)" in traceback
    assert "RuntimeError: boom" in traceback

    _, end_message = writer.session_messages[1]
    assert end_message["type"] == "end"
