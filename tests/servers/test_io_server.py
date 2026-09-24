import json
from collections.abc import Generator

import gevent
import gevent.event
import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.message import SessionMessage
from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.server.io_server import IOServer
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter
from dify_plugin.errors.model import InvokeError


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
        None,
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


SESSION_ID = "session-1"


class RecordingWriter(StdioResponseWriter):
    """Captures the raw wire bytes so the real serialization path is exercised."""

    def __init__(self) -> None:
        self.buffer = ""
        self.done_calls = 0

    def write(self, data: str) -> None:
        self.buffer += data

    def done(self) -> None:
        self.done_calls += 1

    def frames(self) -> list[dict]:
        return [
            json.loads(chunk) for chunk in self.buffer.split("\n\n") if chunk.strip()
        ]

    def session_frames(self) -> list[dict]:
        return [f["data"] for f in self.frames() if f["event"] == "session"]

    def session_frame_types(self) -> list[str]:
        return [f["type"] for f in self.session_frames()]


class SilentReader(StdioRequestReader):
    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        yield from ()


class StubServer(IOServer):
    def __init__(
        self, error: BaseException | None = None, *, block: bool = False
    ) -> None:
        super().__init__(DifyPluginEnv(MAX_WORKER=1), SilentReader(), None)
        self._error = error
        self._block = block

    def _execute_request(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        if self._block:
            gevent.sleep(10)
        if self._error is not None:
            raise self._error


def run_once(server: StubServer) -> RecordingWriter:
    writer = RecordingWriter()
    server._execute_request_in_thread(
        None, SESSION_ID, {}, server.request_reader, writer
    )
    return writer


def test_a_successful_request_is_closed_with_a_single_end_frame() -> None:
    writer = run_once(StubServer())

    assert writer.session_frame_types() == ["end"]
    assert writer.done_calls == 1


def test_an_ordinary_exception_is_reported_then_closed() -> None:
    writer = run_once(StubServer(ValueError("boom")))

    assert writer.session_frame_types() == ["error", "end"]
    error = writer.session_frames()[0]["data"]
    assert error["error_type"] == "ValueError"
    assert error["message"] == "boom"
    assert writer.done_calls == 1


def test_an_invoke_error_still_carries_its_description() -> None:
    writer = run_once(StubServer(InvokeError("unreachable")))

    error = writer.session_frames()[0]["data"]
    assert error["error_type"] == "InvokeError"
    assert error["args"]["description"] == "unreachable"


class Cancelled(BaseException):
    pass


@pytest.mark.parametrize(
    ("error", "error_type"),
    [
        (gevent.Timeout(None), "Timeout"),
        (gevent.GreenletExit(), "GreenletExit"),
        (Cancelled("stop"), "Cancelled"),
    ],
)
def test_a_base_exception_is_reported_then_closed_then_reraised(
    error: BaseException, error_type: str
) -> None:
    """Without this the frame never lands and the caller waits out its whole timeout."""
    writer = RecordingWriter()
    server = StubServer(error)

    with pytest.raises(type(error)):
        server._execute_request_in_thread(
            None, SESSION_ID, {}, server.request_reader, writer
        )

    assert writer.session_frame_types() == ["error", "end"]
    assert writer.session_frames()[0]["data"]["error_type"] == error_type
    assert writer.done_calls == 1


def test_a_killed_worker_greenlet_still_closes_the_session() -> None:
    """The real shape: a cancel arrives while the worker is blocked in provider IO."""
    writer = RecordingWriter()
    server = StubServer(block=True)

    worker = gevent.spawn(
        server._execute_request_in_thread,
        None,
        SESSION_ID,
        {},
        server.request_reader,
        writer,
    )
    gevent.sleep(0)
    worker.kill()

    assert writer.session_frame_types() == ["error", "end"]
    assert writer.session_frames()[0]["data"]["error_type"] == "GreenletExit"
    assert writer.done_calls == 1


class BlockingBodyServer(StubServer):
    def __init__(self) -> None:
        super().__init__()
        self.started = gevent.event.Event()
        self.cleaned = False

    def _execute_request(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        try:
            self.started.set()
            gevent.sleep(30)
        finally:
            self.cleaned = True


def test_a_cancelled_request_is_reported_and_closed_exactly_once() -> None:
    server = BlockingBodyServer()
    writer = RecordingWriter()
    entry = server.cancellations.register(SESSION_ID)

    worker = gevent.spawn(
        server._execute_request_in_thread,
        entry,
        SESSION_ID,
        {},
        server.request_reader,
        writer,
    )
    assert server.started.wait(timeout=2)
    assert server.cancellations.cancel(SESSION_ID) is True
    worker.join(timeout=2)

    assert writer.session_frame_types() == ["error", "end"]
    assert writer.session_frames()[0]["data"]["error_type"] == "RequestCancelledError"
    assert writer.done_calls == 1
    assert server.cleaned


def test_a_finished_request_leaves_nothing_to_cancel() -> None:
    server = StubServer()
    writer = RecordingWriter()
    entry = server.cancellations.register(SESSION_ID)

    server._execute_request_in_thread(
        entry, SESSION_ID, {}, server.request_reader, writer
    )

    assert server.cancellations.cancel(SESSION_ID) is False
    assert writer.session_frame_types() == ["end"]


def parse_frame(payload: dict) -> object:
    reader = StdioRequestReader.__new__(TCPReaderWriter)
    return TCPReaderWriter._parse_line(reader, json.dumps(payload))


def test_an_event_this_version_does_not_know_is_skipped() -> None:
    """A newer daemon must not be able to break an older plugin."""
    assert PluginInStreamEvent.parse("something-new") is None
    assert (
        parse_frame({"session_id": "s", "event": "something-new", "data": {}}) is None
    )


def test_a_cancel_frame_parses_without_a_data_member() -> None:
    frame = parse_frame({"session_id": "s", "event": "cancel"})

    assert frame is not None
    assert frame.event is PluginInStreamEvent.Cancel
    assert frame.data == {}
