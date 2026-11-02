import json
import threading
import traceback
from collections.abc import Callable, Generator, Iterator
from contextvars import ContextVar
from queue import Queue

import gevent
import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.server.__base.filter_reader import FilterReader
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader
from dify_plugin.core.server.serverless.response_writer import ServerlessResponseWriter
from dify_plugin.errors.model import InvokeAuthorizationError
from tests.servers.helpers import (
    CallbackIOServer,
    MemoryRequestReader,
    RecordingResponseWriter,
)


@pytest.fixture
def server() -> Iterator[CallbackIOServer]:
    reader = MemoryRequestReader()
    server = CallbackIOServer(DifyPluginEnv(MAX_WORKER=2), reader, None)
    try:
        yield server
    finally:
        server.close()
        server.executer.shutdown(wait=True)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_success_streams_results_and_ends_once(
    server: CallbackIOServer, count: int
) -> None:
    writer = RecordingResponseWriter()

    def execute(
        session_id: str,
        _data: dict,
        _reader: RequestReader,
        writer: ResponseWriter,
        *_metadata: object,
    ) -> None:
        for index in range(count):
            writer.session_message(session_id, writer.stream_object({"index": index}))

    server.handler = execute
    server._execute_request_in_thread("session-1", {}, server.request_reader, writer)

    assert writer.messages == [
        *[
            {
                "event": "session",
                "session_id": "session-1",
                "data": {"type": "stream", "data": {"index": index}},
            }
            for index in range(count)
        ],
        {
            "event": "session",
            "session_id": "session-1",
            "data": {"type": "end", "data": {}},
        },
    ]
    assert writer.done_count == 1


def test_request_metadata_reaches_execution(server: CallbackIOServer) -> None:
    writer = RecordingResponseWriter()
    received: list[tuple] = []

    def execute(*args: object) -> None:
        received.append(args)

    server.handler = execute
    payload = {"action": "invoke_tool"}
    context = {"credentials": {"tool_credentials": {"provider": "credential-1"}}}
    server._execute_request_in_thread(
        "session-1",
        payload,
        server.request_reader,
        writer,
        "conversation-1",
        "message-1",
        "app-1",
        "endpoint-1",
        context,
    )

    assert received == [
        (
            "session-1",
            payload,
            server.request_reader,
            writer,
            "conversation-1",
            "message-1",
            "app-1",
            "endpoint-1",
            context,
        )
    ]


def test_serverless_execution_preserves_ambient_context(
    server: CallbackIOServer,
) -> None:
    trace: ContextVar[str] = ContextVar("trace")
    token = trace.set("request-trace")
    writer = ServerlessResponseWriter(Queue())
    received = []
    server.handler = lambda *_args: received.append(trace.get())
    try:
        server._execute_request_in_thread("session", {}, server.request_reader, writer)
        assert received == ["request-trace"]
    finally:
        trace.reset(token)
        writer.close()


@pytest.mark.parametrize("after_chunk", [False, True])
@pytest.mark.parametrize("serverless", [False, True])
@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("boom"),
        InvokeAuthorizationError("invalid credentials"),
        gevent.Timeout(None),
        gevent.GreenletExit("cancelled"),
    ],
)
def test_execution_error_preserves_type_message_traceback_and_description(
    server: CallbackIOServer,
    after_chunk: bool,
    serverless: bool,
    error: BaseException,
    caplog: pytest.LogCaptureFixture,
) -> None:
    writer = (
        ServerlessResponseWriter(Queue()) if serverless else RecordingResponseWriter()
    )
    reader = ServerlessRequestReader() if serverless else server.request_reader

    def execute(
        session_id: str,
        _data: dict,
        _reader: RequestReader,
        writer: ResponseWriter,
        *_metadata: object,
    ) -> None:
        if after_chunk:
            writer.session_message(session_id, writer.stream_object({"text": "first"}))
        raise error

    server.handler = execute
    try:
        server.executer.submit(
            server._execute_request_in_thread, "session-1", {}, reader, writer
        ).result(timeout=2)
    finally:
        reader.close()

    if isinstance(writer, ServerlessResponseWriter):
        messages = [json.loads(frame) for frame in iter(writer.q.get_nowait, None)]
        assert writer.q.empty()
        assert writer.closed
    else:
        messages = writer.messages
        assert writer.done_count == 1
    assert [frame["event"] for frame in messages] == ["session"] * len(messages)
    assert [frame["session_id"] for frame in messages] == ["session-1"] * len(messages)
    assert [frame["data"]["type"] for frame in messages] == (
        ["stream", "error", "end"] if after_chunk else ["error", "end"]
    )
    error_data = messages[-2]["data"]["data"]
    assert error_data["error_type"] == type(error).__name__
    assert error_data["message"] == str(error)
    assert "Traceback (most recent call last)" in error_data["args"]["traceback"]
    assert traceback.format_exception_only(error)[-1] in error_data["args"]["traceback"]
    if isinstance(error, InvokeAuthorizationError):
        assert error_data["args"]["description"] == "invalid credentials"
    assert messages[-1]["data"]["data"] == {}
    if serverless:
        assert any(
            record.exc_info and record.exc_info[1] is error for record in caplog.records
        )


@pytest.mark.parametrize("serverless", [False, True])
@pytest.mark.parametrize("cancellation", ["timeout", "kill"])
def test_interruption_finishes_request_and_releases_worker(
    serverless: bool, cancellation: str
) -> None:
    reader = MemoryRequestReader()
    server = CallbackIOServer(DifyPluginEnv(MAX_WORKER=1), reader, None)
    writer = (
        ServerlessResponseWriter(Queue()) if serverless else RecordingResponseWriter()
    )
    entered: Queue = Queue()
    finalized = threading.Event()

    def execute(*_args: object) -> None:
        try:
            if cancellation == "timeout":
                with gevent.Timeout(0.01):
                    gevent.sleep(60)
            else:
                entered.put(gevent.getcurrent())
                gevent.sleep(60)
        finally:
            finalized.set()

    server.handler = execute
    try:
        future = server.executer.submit(
            server._execute_request_in_thread, "interrupted", {}, reader, writer
        )
        if cancellation == "kill":
            entered.get(timeout=2).kill(block=False)
        future.result(timeout=2)
        assert finalized.is_set()

        if isinstance(writer, ServerlessResponseWriter):
            messages = [json.loads(frame) for frame in iter(writer.q.get_nowait, None)]
            assert writer.q.empty()
            assert writer.closed
        else:
            messages = writer.messages
            assert writer.done_count == 1
        assert [frame["data"]["type"] for frame in messages] == ["error", "end"]
        assert messages[0]["data"]["data"]["error_type"] == (
            "Timeout" if cancellation == "timeout" else "GreenletExit"
        )

        server.handler = lambda *_args: None
        next_writer = RecordingResponseWriter()
        server.executer.submit(
            server._execute_request_in_thread, "next", {}, reader, next_writer
        ).result(timeout=2)
        assert [frame["data"]["type"] for frame in next_writer.messages] == ["end"]
        assert next_writer.done_count == 1
    finally:
        server.close()
        server.executer.shutdown(wait=True)


@pytest.mark.parametrize("execution_fails", [False, True])
def test_writer_failure_still_finishes_request(
    server: CallbackIOServer, execution_fails: bool
) -> None:
    class DisconnectedResponseWriter(RecordingResponseWriter):
        def write(self, _data: str) -> None:
            msg = "consumer disconnected"
            raise BrokenPipeError(msg)

    writer = DisconnectedResponseWriter()

    def execute(*_args: object) -> None:
        if execution_fails:
            msg = "model failed"
            raise RuntimeError(msg)

    server.handler = execute
    with pytest.raises(BrokenPipeError, match="consumer disconnected"):
        server._execute_request_in_thread(
            "session-1", {}, server.request_reader, writer
        )

    assert writer.done_count == 1


def test_run_dispatches_only_requests_with_all_metadata_until_reader_closes(
    server: CallbackIOServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    subscribed = threading.Event()
    read = server.request_reader.read
    read_stream = server.request_reader._read_stream
    received: Queue[tuple] = Queue()

    def subscribe(predicate: Callable[[PluginInStream], bool]) -> FilterReader:
        reader = read(predicate)
        subscribed.set()
        return reader

    def execute(*args: object) -> None:
        received.put(args)

    def stream() -> Generator[PluginInStream, None, None]:
        assert subscribed.wait(timeout=2)
        yield from read_stream()
        server.request_reader.close()

    monkeypatch.setattr(server.request_reader, "read", subscribe)
    monkeypatch.setattr(server.request_reader, "_read_stream", stream)
    server.handler = execute
    listener = threading.Thread(target=server.run, daemon=True)
    requests = [
        PluginInStream(
            session_id=session_id,
            event=event,
            data={"action": "invoke_tool"},
            reader=server.request_reader,
            writer=RecordingResponseWriter(),
            conversation_id=f"conversation-{session_id}",
            message_id=f"message-{session_id}",
            app_id=f"app-{session_id}",
            endpoint_id=f"endpoint-{session_id}",
            context={"credentials": {}},
        )
        for session_id, event in (
            ("one", PluginInStreamEvent.Request),
            ("ignored", PluginInStreamEvent.BackwardInvocationResponse),
            ("two", PluginInStreamEvent.Request),
        )
    ]
    assert isinstance(server.request_reader, MemoryRequestReader)
    server.request_reader.inputs.extend(requests)
    try:
        listener.start()
        listener.join(timeout=2)
        assert not listener.is_alive()
    finally:
        server.close()
        listener.join(timeout=2)
        server.executer.shutdown(wait=True)

    assert not listener.is_alive()
    actual = [received.get_nowait() for _ in range(received.qsize())]
    assert sorted(actual) == [
        (
            request.session_id,
            request.data,
            request.reader,
            request.writer,
            request.conversation_id,
            request.message_id,
            request.app_id,
            request.endpoint_id,
            request.context,
        )
        for request in (requests[0], requests[2])
    ]
    assert [request.writer.done_count for request in requests] == [1, 0, 1]


def test_heartbeat_requires_default_writer(server: CallbackIOServer) -> None:
    with pytest.raises(RuntimeError, match="Default writer is required"):
        server._heartbeat()


def test_heartbeat_continues_after_transient_write_failure(
    server: CallbackIOServer,
) -> None:
    published: Queue[None] = Queue()

    class RecoveringWriter(RecordingResponseWriter):
        def __init__(self) -> None:
            super().__init__()
            self.failed = False

        def write(self, data: str) -> None:
            if not self.failed:
                self.failed = True
                msg = "temporary write failure"
                raise OSError(msg)
            super().write(data)
            published.put(None)

    writer = RecoveringWriter()
    server.default_writer = writer
    server.config = DifyPluginEnv(MAX_WORKER=2, HEARTBEAT_INTERVAL=0.001)
    heartbeat = gevent.spawn(server._heartbeat)
    try:
        published.get(timeout=2)
        published.get(timeout=2)
    finally:
        heartbeat.kill(block=True, timeout=2)

    assert len(writer.messages) >= 2
    assert all(
        frame == {"event": "heartbeat", "session_id": None, "data": {}}
        for frame in writer.messages
    )
    assert heartbeat.dead
