import json
from collections.abc import Callable, Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import gevent
import httpx
import pytest
from gevent.event import Event
from pydantic import BaseModel, ValidationError

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.runtime import BackwardsInvocation, Session
from dify_plugin.core.utils.http import httpx_client
from tests.http_server import Response, TestHTTPServer
from tests.servers.helpers import MemoryRequestReader, RecordingResponseWriter


class Result(BaseModel):
    answer: str


class DaemonWriter(RecordingResponseWriter):
    def __init__(self, on_request: Callable[[dict], None]) -> None:
        super().__init__()
        self.on_request = on_request

    def write(self, data: str) -> None:
        super().write(data)
        if data.strip():
            self.on_request(json.loads(data))


@pytest.fixture
def session() -> Generator[Session]:
    reader = MemoryRequestReader()
    with ThreadPoolExecutor(max_workers=1) as executor:
        session = Session(
            session_id="session-a",
            executor=executor,
            reader=reader,
            writer=RecordingResponseWriter(),
            install_method=InstallMethod.Local,
            dify_plugin_daemon_url="http://daemon.example",
            max_invocation_timeout=2,
        )
        try:
            yield session
        finally:
            reader.close()


@pytest.fixture
def invocation(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> BackwardsInvocation[Result]:
    invocation = BackwardsInvocation[Result](session)
    monkeypatch.setattr(
        invocation, "_generate_backwards_request_id", lambda: "request-a"
    )
    return invocation


def _response(
    session: Session,
    data: dict | None = None,
    *,
    request_id: str = "request-a",
    event: str = "response",
    message: str = "",
) -> PluginInStream:
    # daemon 635d262e: session_manager/session.go and backwards_invocation/entities.go.
    return PluginInStream(
        session_id=session.session_id,
        event=PluginInStreamEvent.BackwardInvocationResponse,
        data={
            "backwards_request_id": request_id,
            "event": event,
            "message": message,
            "data": data,
        },
        reader=session.reader,
        writer=session.writer,
    )


def _wire(chunk: PluginInStream) -> bytes:
    return (
        json.dumps(
            {
                "session_id": chunk.session_id,
                "event": chunk.event.value,
                "data": chunk.data,
            },
            ensure_ascii=False,
        ).encode()
        + b"\n\n"
    )


def _chunks(*chunks: PluginInStream | None) -> Generator[PluginInStream | None]:
    yield from chunks


class ResponseStream(httpx.SyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self.chunks = chunks
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        yield from self.chunks

    def close(self) -> None:
        self.closed = True


def _http_client(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    *chunks: bytes,
) -> tuple[httpx.Client, ResponseStream]:
    session.install_method = InstallMethod.Serverless
    stream = ResponseStream(chunks)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=stream)
        )
    )
    monkeypatch.setattr("dify_plugin.core.runtime.httpx_client", lambda: client)
    return client, stream


@pytest.mark.parametrize("install_method", [InstallMethod.Local, InstallMethod.Remote])
def test_backwards_invoke_receives_immediate_response(
    session: Session,
    invocation: BackwardsInvocation[Result],
    install_method: InstallMethod,
) -> None:
    session.install_method = install_method

    def respond(request: dict) -> None:
        assert request == {
            "event": "session",
            "session_id": "session-a",
            "data": {
                "type": "invoke",
                "data": {
                    "type": "storage",
                    "backwards_request_id": "request-a",
                    "request": {"opt": "get", "key": "你好"},
                },
            },
        }
        session.reader._process_line(_response(session, {"answer": "stored"}))
        session.reader._process_line(_response(session, event="end"))

    session.writer = DaemonWriter(respond)
    with gevent.Timeout(3):
        result = list(
            invocation._backwards_invoke(
                InvokeType.Storage, Result, {"opt": "get", "key": "你好"}
            )
        )
    assert result == [Result(answer="stored")]
    assert session.reader.readers == []


def test_backwards_requests_do_not_share_results(session: Session) -> None:
    sent = Event()

    def record_request(_request: dict) -> None:
        if len(writer.messages) == 2:
            sent.set()

    writer = DaemonWriter(record_request)
    session.writer = writer
    other = Session(
        session_id="session-b",
        executor=session._executor,
        reader=session.reader,
        writer=session.writer,
        install_method=InstallMethod.Remote,
        max_invocation_timeout=2,
    )

    def invoke(active_session: Session) -> list[Result]:
        return list(
            BackwardsInvocation[Result](active_session)._backwards_invoke(
                InvokeType.Storage, Result, {"key": active_session.session_id}
            )
        )

    workers = [gevent.spawn(invoke, active) for active in (session, other)]
    try:
        assert sent.wait(timeout=2), "backwards requests were not sent"
        ids = {
            frame["session_id"]: frame["data"]["data"]["backwards_request_id"]
            for frame in writer.messages
        }
        assert len(set(ids.values())) == 2
        session.reader._process_line(
            _response(session, {"answer": "unrelated"}, request_id="unknown")
        )
        session.reader._process_line(
            _response(
                other, {"answer": "wrong session"}, request_id=ids[session.session_id]
            )
        )
        session.reader._process_line(
            PluginInStream(
                session_id=session.session_id,
                event=PluginInStreamEvent.Request,
                data={"backwards_request_id": ids[session.session_id]},
                reader=session.reader,
                writer=session.writer,
            )
        )
        for active, answer in (
            (other, "b-first"),
            (session, "a-first"),
            (other, "b-last"),
        ):
            session.reader._process_line(
                _response(active, {"answer": answer}, request_id=ids[active.session_id])
            )
        session.reader._process_line(
            _response(other, event="end", request_id=ids[other.session_id])
        )
        session.reader._process_line(
            _response(session, event="end", request_id=ids[session.session_id])
        )
        assert workers[0].get(timeout=2) == [Result(answer="a-first")]
        assert workers[1].get(timeout=2) == [
            Result(answer="b-first"),
            Result(answer="b-last"),
        ]
        assert session.reader.readers == []
    finally:
        gevent.killall(workers, block=True, timeout=2)


def test_cancelling_waiting_invocation_removes_subscription(session: Session) -> None:
    sent = Event()
    session.writer = DaemonWriter(lambda _request: sent.set())
    worker = gevent.spawn(
        lambda: list(
            BackwardsInvocation(session)._backwards_invoke(InvokeType.Storage, dict, {})
        )
    )
    try:
        assert sent.wait(timeout=2)
        assert len(session.reader.readers) == 1
        worker.kill(block=True, timeout=2)
        assert worker.dead
        assert session.reader.readers == []
    finally:
        worker.kill(block=True, timeout=2)


def test_send_failure_removes_subscription(
    session: Session, invocation: BackwardsInvocation[Result]
) -> None:
    class FailedWriter(RecordingResponseWriter):
        def write(self, _data: str) -> None:
            msg = "daemon disconnected"
            raise BrokenPipeError(msg)

    session.writer = FailedWriter()
    with pytest.raises(BrokenPipeError, match="daemon disconnected"):
        list(invocation._backwards_invoke(InvokeType.Storage, Result, {}))
    assert session.reader.readers == []


@pytest.mark.parametrize("ending", ["end", "error", "close", "invalid-result"])
def test_full_duplex_releases_subscription_on_every_exit(
    session: Session, invocation: BackwardsInvocation[Result], ending: str
) -> None:
    terminal = {
        "end": _response(session, event="end"),
        "error": _response(session, event="error", message="permission denied"),
        "invalid-result": _response(session, {"answer": []}),
        "close": _response(session, {"answer": "unconsumed"}),
    }[ending]

    def respond(_request: dict) -> None:
        session.reader._process_line(_response(session, {"answer": "first"}))
        session.reader._process_line(terminal)

    session.writer = DaemonWriter(respond)
    with closing(
        invocation._backwards_invoke(InvokeType.Storage, Result, {})
    ) as stream:
        assert next(stream) == Result(answer="first")
        assert len(session.reader.readers) == 1
        if ending == "end":
            assert list(stream) == []
        elif ending == "close":
            stream.close()
        else:
            message = "permission denied" if ending == "error" else "Failed to parse"
            with pytest.raises(Exception, match=message):
                next(stream)
        assert session.reader.readers == []


def test_reader_disconnect_unblocks_waiting_backwards_invocation(
    session: Session, invocation: BackwardsInvocation[Result]
) -> None:
    sent = Event()
    session.writer = DaemonWriter(lambda _request: sent.set())
    worker = gevent.spawn(
        lambda: list(invocation._backwards_invoke(InvokeType.Storage, Result, {}))
    )
    try:
        assert sent.wait(timeout=2)
        session.reader.close()
        assert worker.get(timeout=2) == []
        assert session.reader.readers == []
    finally:
        worker.kill(block=True, timeout=2)


def test_data_resets_consecutive_empty_response_timeout(
    session: Session, invocation: BackwardsInvocation[Result]
) -> None:
    result = invocation._line_converter_wrapper(
        _chunks(
            None,
            _response(session, {"answer": "first"}),
            None,
            _response(session, {"answer": "second"}),
            _response(session, event="end"),
            _response(session, {"answer": "after end"}),
        ),
        Result,
    )
    assert list(result) == [Result(answer="first"), Result(answer="second")]


def test_empty_response_count_preserves_timeout_exception(
    session: Session,
    invocation: BackwardsInvocation[Result],
) -> None:
    session.max_invocation_timeout = 2
    with pytest.raises(Exception, match="without response after 2 seconds") as error:
        list(invocation._line_converter_wrapper(_chunks(None, None), Result))
    assert type(error.value) is Exception


def test_invocation_timeout_resets_for_results_and_excludes_consumer_time(
    session: Session,
    invocation: BackwardsInvocation[Result],
) -> None:
    session.max_invocation_timeout = 0.1

    def respond() -> Generator[PluginInStream]:
        for text in ("first", "second"):
            gevent.sleep(0.06)
            yield _response(session, {"answer": text})
        yield _response(session, event="end")

    stream = invocation._line_converter_wrapper(respond(), Result)
    assert next(stream) == Result(answer="first")
    gevent.sleep(0.15)
    assert list(stream) == [Result(answer="second")]


@pytest.mark.parametrize("terminal_event", ["end", "response"])
def test_null_response_terminates_without_constructing_result(
    session: Session,
    invocation: BackwardsInvocation[Result],
    terminal_event: str,
) -> None:
    assert (
        list(
            invocation._line_converter_wrapper(
                _chunks(_response(session, event=terminal_event)), Result
            )
        )
        == []
    )


def test_daemon_error_preserves_timeout_phase(
    session: Session, invocation: BackwardsInvocation[Result]
) -> None:
    message = "invoke llm failed: phase=read_idle timeout_ms=240000"
    with pytest.raises(Exception, match=message):
        list(
            invocation._line_converter_wrapper(
                _chunks(_response(session, event="error", message=message)), Result
            )
        )


def test_invalid_result_retains_validation_cause(
    session: Session, invocation: BackwardsInvocation[Result]
) -> None:
    with pytest.raises(Exception, match="Failed to parse response") as exc:
        list(
            invocation._line_converter_wrapper(
                _chunks(_response(session, {"answer": []})), Result
            )
        )
    assert isinstance(exc.value.__cause__, ValidationError)


def test_missing_session_cannot_start_backwards_invocation() -> None:
    with pytest.raises(Exception, match="does not support backwards invoke"):
        BackwardsInvocation()._backwards_invoke(InvokeType.Storage, dict, {})


def test_serverless_invocation_requires_daemon_url(session: Session) -> None:
    session.install_method = InstallMethod.Serverless
    session.dify_plugin_daemon_url = None
    with pytest.raises(Exception, match="does not support backwards invoke"):
        list(
            BackwardsInvocation(session)._backwards_invoke(InvokeType.Storage, dict, {})
        )


@pytest.mark.parametrize(
    "ending", ["end", "error", "invalid-json", "close", "consumer-error", "eof"]
)
def test_http_stream_is_closed_on_every_exit(
    session: Session,
    invocation: BackwardsInvocation[Result],
    monkeypatch: pytest.MonkeyPatch,
    ending: str,
) -> None:
    end = {
        "end": _wire(_response(session, event="end")),
        "error": _wire(_response(session, event="error", message="permission denied")),
        "invalid-json": b"not-json\n",
        "eof": b"",
        "close": b"",
        "consumer-error": b"",
    }[ending]
    client, response_stream = _http_client(
        session, monkeypatch, _wire(_response(session, {"answer": "first"})), end
    )
    with closing(
        invocation._backwards_invoke(InvokeType.Storage, Result, {})
    ) as stream:
        assert next(stream) == Result(answer="first")
        assert not response_stream.closed
        if ending == "end":
            assert list(stream) == []
        elif ending == "error":
            with pytest.raises(Exception, match="permission denied"):
                next(stream)
        elif ending == "invalid-json":
            with pytest.raises(ValidationError, match="Invalid JSON"):
                next(stream)
        elif ending == "eof":
            assert list(stream) == []
        elif ending == "consumer-error":
            with pytest.raises(
                Exception, match="Failed to parse response: consumer stopped"
            ) as error:
                stream.throw(ValueError("consumer stopped"))
            assert isinstance(error.value.__cause__, ValueError)
        else:
            stream.close()
        assert response_stream.closed
        assert client.is_closed


@pytest.mark.integration
def test_http_backwards_invocation_uses_daemon_wire_protocol(
    session: Session,
    invocation: BackwardsInvocation[Result],
    http_server: Callable[[list[Response]], TestHTTPServer],
) -> None:
    session.install_method = InstallMethod.Serverless
    body = (
        b"\n\n"
        + _wire(_response(session, {"answer": "你好"}))
        + _wire(_response(session, event="end"))
    )
    # A Unicode code point and the frame delimiter both cross HTTP chunk boundaries.
    boundary = body.index("你".encode()) + 1
    server = http_server([
        Response(
            headers={"Content-Type": "text/event-stream"},
            chunks=(body[:boundary], body[boundary:-1], body[-1:]),
        )
    ])
    session.dify_plugin_daemon_url = server.url + "/prefix/"
    assert list(
        invocation._backwards_invoke(
            InvokeType.Storage, Result, {"opt": "get", "key": "你好"}
        )
    ) == [Result(answer="你好")]
    assert len(server.requests) == 1
    request = server.requests[0]
    assert request.method == "POST"
    assert request.path == "/prefix/backwards-invocation/transaction"
    assert request.headers["Dify-Plugin-Session-ID"] == session.session_id
    assert request.body.endswith(b"\n\n")
    assert json.loads(request.body) == {
        "event": "session",
        "session_id": "session-a",
        "data": {
            "type": "invoke",
            "data": {
                "type": "storage",
                "backwards_request_id": "request-a",
                "request": {"opt": "get", "key": "你好"},
            },
        },
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (
            400,
            (
                b'{"backwards_request_id":"request-a","event":"error",'
                b'"message":"failed to get session info from cache",'
                b'"data":{"error_type":"SessionNotFound"}}'
            ),
            KeyError,
        ),
        (401, b"", None),
        (429, b"", None),
        (500, b"failed to parse request", ValidationError),
    ],
)
def test_http_status_preserves_response_parsing(
    session: Session,
    invocation: BackwardsInvocation[Result],
    http_server: Callable[[list[Response]], TestHTTPServer],
    status: int,
    body: bytes,
    error: type[Exception] | None,
) -> None:
    session.install_method = InstallMethod.Serverless
    session.dify_plugin_daemon_url = http_server([
        Response(status=status, body=body)
    ]).url
    stream = invocation._backwards_invoke(InvokeType.Storage, Result, {})
    if error is None:
        assert list(stream) == []
    else:
        with pytest.raises(error):
            list(stream)


@pytest.mark.integration
def test_http_read_timeout_releases_response(
    session: Session,
    invocation: BackwardsInvocation[Result],
    monkeypatch: pytest.MonkeyPatch,
    http_server: Callable[[list[Response]], TestHTTPServer],
) -> None:
    session.install_method = InstallMethod.Serverless
    session.max_invocation_timeout = 1
    session.dify_plugin_daemon_url = http_server([
        Response(body=_wire(_response(session, event="end")), delay=2)
    ]).url
    responses: list[httpx.Response] = []
    client = httpx_client()
    client.event_hooks["response"].append(responses.append)
    monkeypatch.setattr("dify_plugin.core.runtime.httpx_client", lambda: client)
    with gevent.Timeout(3), pytest.raises(httpx.ReadTimeout):
        list(invocation._backwards_invoke(InvokeType.Storage, Result, {}))
    assert len(responses) == 1
    assert responses[0].is_closed
    assert client.is_closed


@pytest.mark.integration
def test_http_transport_failure_does_not_complete_partial_result(
    session: Session,
    invocation: BackwardsInvocation[Result],
    http_server: Callable[[list[Response]], TestHTTPServer],
) -> None:
    session.install_method = InstallMethod.Serverless
    body = _wire(_response(session, {"answer": "partial"}))
    server = http_server([
        Response(headers={"Content-Length": str(len(body) + 1)}, body=body)
    ])
    session.dify_plugin_daemon_url = server.url
    with closing(
        invocation._backwards_invoke(InvokeType.Storage, Result, {})
    ) as stream:
        assert next(stream) == Result(answer="partial")
        with pytest.raises(httpx.RemoteProtocolError, match="complete message body"):
            next(stream)


@pytest.mark.integration
def test_http_heartbeats_keep_the_stream_open(
    session: Session,
    invocation: BackwardsInvocation[Result],
    http_server: Callable[[list[Response]], TestHTTPServer],
) -> None:
    session.install_method = InstallMethod.Serverless
    session.max_invocation_timeout = 0.1
    session.dify_plugin_daemon_url = http_server([
        Response(
            chunks=(*([b"\n\n"] * 10), _wire(_response(session, event="end"))),
            delay=0.03,
        )
    ]).url

    with gevent.Timeout(2):
        assert list(invocation._backwards_invoke(InvokeType.Storage, Result, {})) == []
