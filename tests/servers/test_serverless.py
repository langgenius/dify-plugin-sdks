import json
import socket
import struct
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.client import HTTPConnection
from queue import Queue
from threading import Thread, current_thread
from types import SimpleNamespace
from unittest.mock import patch

import gevent
import pytest
from flask import Flask, Response
from gevent.event import Event
from gevent.pywsgi import WSGIServer
from werkzeug.serving import BaseWSGIServer, make_server

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.io import PluginInStreamEvent
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.serverless import request_reader as serverless_module
from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader
from tests.servers.helpers import CallbackIOServer


@pytest.fixture
def reader() -> Iterator[ServerlessRequestReader]:
    reader = ServerlessRequestReader(max_single_connection_lifetime=1)
    reader.app.route("/invoke", methods=["POST"])(reader.handler)
    reader.app.route("/health", methods=["GET"])(reader.health)
    try:
        yield reader
    finally:
        reader.close()


def handle_request(reader: ServerlessRequestReader) -> Response:
    with reader.app.test_request_context(
        json={"event": "request", "session_id": "session", "data": {}},
    ):
        response, status = reader.handler()

    assert isinstance(response, Generator)
    assert status == 200
    return Response(response, status=status)


def test_health_and_http_methods(reader: ServerlessRequestReader) -> None:
    client = reader.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"OK"
    assert client.get("/invoke").status_code == 405
    assert client.post("/health").status_code == 405
    assert reader.request_queue.empty()


@pytest.mark.parametrize("use_gevent", [False, True])
def test_launch_serves_requests_and_close_stops_the_http_thread(
    monkeypatch: pytest.MonkeyPatch,
    use_gevent: bool,
) -> None:
    reader = ServerlessRequestReader(host="127.0.0.1", port=0)
    created = Event()
    servers: list[tuple[WSGIServer | BaseWSGIServer, Thread]] = []

    def create_server(listener: tuple[str, int], app: Flask) -> WSGIServer:
        server = WSGIServer(listener, app, log=None)
        servers.append((server, current_thread()))
        created.set()
        return server

    def create_threaded_server(
        host: str, port: int, app: Flask, *, threaded: bool
    ) -> BaseWSGIServer:
        server = make_server(host, port, app, threaded=threaded)
        servers.append((server, current_thread()))
        created.set()
        return server

    if use_gevent:
        monkeypatch.setattr(serverless_module, "WSGIServer", create_server)
    else:
        monkeypatch.setattr(
            serverless_module, "socket", SimpleNamespace(socket=object())
        )
        monkeypatch.setattr(serverless_module, "make_server", create_threaded_server)
    reader.launch()
    client = None
    try:
        assert created.wait(timeout=2)
        server, thread = servers[0]
        if use_gevent:
            with gevent.Timeout(2):
                while not server.started:
                    gevent.sleep(0.001)
        with closing(
            HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        ) as http:
            http.request("GET", "/health")
            response = http.getresponse()
            assert response.status == 200
            assert response.read() == b"OK"

            def invoke() -> tuple[int, bytes]:
                http.request(
                    "POST",
                    "/invoke",
                    json.dumps({
                        "event": "request",
                        "session_id": "launched-server",
                        "data": {"text": "你好"},
                    }),
                    {"Content-Type": "application/json"},
                )
                result = http.getresponse()
                return result.status, result.read()

            client = gevent.spawn(invoke)
            request = reader.request_queue.get(timeout=2)
            assert request.session_id == "launched-server"
            assert request.data == {"text": "你好"}
            request.writer.session_message(
                request.session_id, request.writer.stream_object(request.data)
            )
            request.writer.session_message(
                request.session_id, request.writer.stream_end_object()
            )
            request.writer.done()
            status, body = client.get(timeout=2)
            assert status == 200
            assert [json.loads(line) for line in body.splitlines() if line] == [
                {
                    "event": "session",
                    "session_id": "launched-server",
                    "data": {"type": "stream", "data": {"text": "你好"}},
                },
                {
                    "event": "session",
                    "session_id": "launched-server",
                    "data": {"type": "end", "data": {}},
                },
            ]

        reader.close()
        thread.join(timeout=1)
        assert not thread.is_alive()
        if use_gevent:
            assert not server.started
        else:
            assert server.socket.fileno() == -1
    finally:
        reader.close()
        if client is not None:
            client.kill(block=True, timeout=1)
        for server, thread in servers:
            if use_gevent:
                server.stop(timeout=1)
            else:
                server.shutdown()
                server.server_close()
            thread.join(timeout=1)
            assert not thread.is_alive()


def test_launch_uses_app_and_handler_replaced_after_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = ServerlessRequestReader(host="127.0.0.1", port=0)
    reader.app = Flask("replacement")
    reader.handler = lambda: ("custom response", 202)
    created: Queue[tuple[WSGIServer, Thread]] = Queue()

    def create_server(listener: tuple[str, int], app: Flask) -> WSGIServer:
        server = WSGIServer(listener, app, log=None)
        created.put((server, current_thread()))
        return server

    monkeypatch.setattr(serverless_module, "WSGIServer", create_server)
    reader.launch()
    server, thread = created.get(timeout=2)
    try:
        with gevent.Timeout(2):
            while not server.started:
                gevent.sleep(0.001)
        with closing(
            HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        ) as http:
            http.request("POST", "/invoke")
            response = http.getresponse()
            assert response.status == 202
            assert response.read() == b"custom response"
            http.request("GET", "/health")
            response = http.getresponse()
            assert response.status == 200
            assert response.read() == b"OK"
        assert reader.request_queue.empty()
    finally:
        reader.close()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert not server.started


def test_invoke_preserves_metadata_and_response_frames(
    reader: ServerlessRequestReader,
) -> None:
    payload = {
        "event": "request",
        "session_id": "session-1",
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "app_id": "app-1",
        "endpoint_id": "endpoint-1",
        "context": {"credentials": {"tool_credentials": {"provider": "credential-1"}}},
        "data": {
            "type": "tool",
            "action": "invoke_tool",
            "tool_parameters": {"text": "你好"},
        },
    }
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            reader.app.test_client().post, "/invoke", json=payload, buffered=True
        )
        plugin_in = reader.request_queue.get(timeout=2)
        plugin_in.writer.session_message(
            "session-1", plugin_in.writer.stream_object({"text": "你好"})
        )
        plugin_in.writer.session_message(
            "session-1", plugin_in.writer.stream_end_object()
        )
        plugin_in.writer.done()
        response = future.result(timeout=2)

    assert plugin_in.event is PluginInStreamEvent.Request
    for key in (
        "session_id",
        "conversation_id",
        "message_id",
        "app_id",
        "endpoint_id",
        "context",
        "data",
    ):
        assert getattr(plugin_in, key) == payload[key]
    assert plugin_in.reader is reader
    assert response.status_code == 200
    assert response.data.endswith(b"\n\n")
    assert [json.loads(line) for line in response.data.splitlines() if line] == [
        {
            "event": "session",
            "session_id": "session-1",
            "data": {"type": "stream", "data": {"text": "你好"}},
        },
        {
            "event": "session",
            "session_id": "session-1",
            "data": {"type": "end", "data": {}},
        },
    ]
    response.close()


def test_connections_keep_their_own_responses(reader: ServerlessRequestReader) -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            session_id: executor.submit(
                reader.app.test_client().post,
                "/invoke",
                json={"event": "request", "session_id": session_id, "data": {}},
                buffered=True,
            )
            for session_id in ("one", "two")
        }
        requests = [reader.request_queue.get(timeout=2) for _ in range(2)]
        for index in range(2):
            for plugin_in in requests:
                plugin_in.writer.write(f"{plugin_in.session_id}:{index}\n")
        for plugin_in in requests:
            plugin_in.writer.done()
        responses = {
            session_id: future.result(timeout=2)
            for session_id, future in futures.items()
        }

    for session_id, response in responses.items():
        assert response.data.decode() == f"{session_id}:0\n{session_id}:1\n"
        response.close()


def test_event_loop_delivers_http_request_and_stops_after_close(
    reader: ServerlessRequestReader,
) -> None:
    subscriber = reader.read(
        lambda message: message.event is PluginInStreamEvent.Request
    )
    loop = gevent.spawn(reader.event_loop)
    client = gevent.spawn(
        reader.app.test_client().post,
        "/invoke",
        json={"event": "request", "session_id": "through-loop", "data": {"value": 1}},
        buffered=True,
    )
    response = None
    try:
        request = next(subscriber.read(timeout_for_round=1))
        assert request is not None
        assert request.session_id == "through-loop"
        assert request.data == {"value": 1}
        request.writer.session_message(
            request.session_id, request.writer.stream_end_object()
        )
        request.writer.done()
        response = client.get(timeout=1)
        assert response.status_code == 200
        assert json.loads(response.data)["data"] == {"type": "end", "data": {}}

        reader.close()

        loop.get(timeout=1)
        assert reader.readers == []
        assert list(subscriber.read()) == []
    finally:
        if response is not None:
            response.close()
        reader.close()
        client.kill(block=True, timeout=1)
        loop.kill(block=True, timeout=1)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"event": "unknown", "session_id": "session", "data": {}},
        {"event": "request", "session_id": "session"},
        {"event": "request", "data": {}},
    ],
)
def test_invalid_request_is_rejected_before_enqueue(
    reader: ServerlessRequestReader,
    payload: object,
) -> None:
    with reader.app.test_request_context(
        data=json.dumps(payload), content_type="application/json"
    ):
        response, status = reader.handler()

    if not isinstance(response, str):
        response.close()
    assert status >= 400
    assert reader.request_queue.empty()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", []),
        ("session_id", 1),
        ("data", []),
        ("data", None),
        ("context", []),
        ("app_id", 1),
    ],
)
def test_request_fields_reach_the_router_without_additional_validation(
    reader: ServerlessRequestReader, field: str, value: object
) -> None:
    payload = {"event": "request", "session_id": "session", "data": {}, field: value}
    with reader.app.test_request_context(json=payload):
        response, status = reader.handler()
    try:
        assert status == 200
        request = reader.request_queue.get_nowait()
        assert getattr(request, field) == value
    finally:
        response.close()


@pytest.mark.parametrize(
    ("body", "content_type"), [("{", "application/json"), ("text", "text/plain")]
)
def test_invalid_http_body_is_rejected(
    reader: ServerlessRequestReader,
    body: str,
    content_type: str,
) -> None:
    response = reader.app.test_client().post(
        "/invoke", data=body, content_type=content_type
    )
    assert response.status_code >= 400
    assert reader.request_queue.empty()


def test_enqueue_error_returns_failure(reader: ServerlessRequestReader) -> None:
    with patch.object(reader, "request_queue") as queue:
        queue.put.side_effect = RuntimeError("enqueue failed")
        response = reader.app.test_client().post(
            "/invoke", json={"event": "request", "session_id": "session", "data": {}}
        )

    assert response.status_code == 500
    assert b"enqueue failed" in response.data


def test_done_finishes_once_and_discards_late_writes(
    reader: ServerlessRequestReader,
) -> None:
    response = handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()
    plugin_in.writer.write("chunk")
    plugin_in.writer.done()
    plugin_in.writer.done()
    plugin_in.writer.write("late")

    assert list(response.response) == ["chunk"]
    assert plugin_in.writer.q.empty()


def test_consumer_close_releases_buffer_and_stops_future_writes(
    reader: ServerlessRequestReader,
) -> None:
    response = handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()
    plugin_in.writer.write("first")
    assert next(iter(response.response)) == "first"
    plugin_in.writer.write("buffered")

    response.close()
    plugin_in.writer.write("late")
    plugin_in.writer.done()

    assert plugin_in.writer.q.empty()


def test_consumer_close_before_first_chunk_stops_writes(
    reader: ServerlessRequestReader,
) -> None:
    response = handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()

    response.close()
    plugin_in.writer.write("late")
    plugin_in.writer.done()

    assert plugin_in.writer.q.empty()


def test_idle_timeout_resets_after_each_response(
    reader: ServerlessRequestReader,
) -> None:
    reader.max_single_connection_lifetime = 0.2
    response = handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()

    def produce() -> None:
        for text in ("first", "second", "third"):
            plugin_in.writer.write(text)
            gevent.sleep(0.125)
        plugin_in.writer.done()

    worker = gevent.spawn(produce)
    try:
        assert list(response.response) == ["first", "second", "third"]
        worker.get(timeout=1)
    finally:
        response.close()
        worker.kill()


def test_idle_timeout_preserves_partial_result_and_ends_silently(
    reader: ServerlessRequestReader,
) -> None:
    reader.max_single_connection_lifetime = 0.02
    response = handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()
    plugin_in.writer.session_message(
        "session", plugin_in.writer.stream_object({"text": "partial"})
    )

    messages = [json.loads(frame)["data"] for frame in response.response]

    assert [message["type"] for message in messages] == ["stream"]
    assert messages[0]["data"] == {"text": "partial"}
    assert plugin_in.writer.closed
    assert plugin_in.writer.q.empty()


def test_wsgi_response_close_stops_producer_buffering(
    reader: ServerlessRequestReader,
) -> None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            reader.app.test_client().post,
            "/invoke",
            json={"event": "request", "session_id": "session", "data": {}},
            buffered=False,
        )
        plugin_in = reader.request_queue.get(timeout=2)
        plugin_in.writer.write("first")
        response = future.result(timeout=2)

    assert next(iter(response.response)) == b"first"
    plugin_in.writer.write("buffered")
    response.close()
    plugin_in.writer.write("late")
    assert plugin_in.writer.q.empty()


@pytest.mark.integration
def test_http_socket_delivers_complete_session_frames(
    reader: ServerlessRequestReader,
) -> None:
    server = WSGIServer(("127.0.0.1", 0), reader.app, log=None)
    server.start()

    def produce() -> None:
        plugin_in = reader.request_queue.get(timeout=2)
        try:
            plugin_in.writer.session_message(
                plugin_in.session_id,
                plugin_in.writer.stream_object({"text": "你好"}),
            )
            plugin_in.writer.session_message(
                plugin_in.session_id, plugin_in.writer.stream_end_object()
            )
        finally:
            plugin_in.writer.done()

    try:
        with (
            ThreadPoolExecutor(max_workers=1) as executor,
            closing(
                HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            ) as connection,
        ):
            worker = executor.submit(produce)
            connection.request(
                "POST",
                "/invoke",
                body=json.dumps({
                    "event": "request",
                    "session_id": "socket-session",
                    "data": {},
                }),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            body = response.read()
            worker.result(timeout=2)
            assert response.status == 200
    finally:
        server.stop(timeout=2)

    assert body.endswith(b"\n\n")
    assert [json.loads(line) for line in body.splitlines() if line] == [
        {
            "event": "session",
            "session_id": "socket-session",
            "data": {"type": "stream", "data": {"text": "你好"}},
        },
        {
            "event": "session",
            "session_id": "socket-session",
            "data": {"type": "end", "data": {}},
        },
    ]


@pytest.mark.parametrize("close_before_start", [False, True])
def test_closed_response_cancels_execution_or_prevents_it_from_starting(
    reader: ServerlessRequestReader,
    close_before_start: bool,
) -> None:
    entered, finalized = Event(), Event()
    server = CallbackIOServer(DifyPluginEnv(MAX_WORKER=1), reader, None)

    def execute(*_args: object) -> None:
        entered.set()
        try:
            gevent.sleep(60)
        finally:
            finalized.set()

    server.handler = execute
    response = handle_request(reader)
    request = reader.request_queue.get_nowait()
    if close_before_start:
        response.close()
    try:
        future = server.executer.submit(
            server._execute_request_in_thread,
            request.session_id,
            request.data,
            reader,
            request.writer,
        )
        if not close_before_start:
            assert entered.wait(timeout=1)
            response.close()
        future.result(timeout=1)
        assert entered.is_set() is not close_before_start
        assert finalized.is_set() is not close_before_start
        assert request.writer.q.empty()
    finally:
        response.close()
        server.executer.shutdown(wait=True)


@pytest.mark.integration
def test_http_disconnect_releases_worker_for_next_request(
    reader: ServerlessRequestReader,
) -> None:
    finalized = Event()
    server = CallbackIOServer(DifyPluginEnv(MAX_WORKER=1), reader, None)
    http = WSGIServer(("127.0.0.1", 0), reader.app, log=None)
    http.start()

    def execute(
        session_id: str,
        _data: dict,
        _reader: RequestReader,
        writer: ResponseWriter,
        *_metadata: object,
    ) -> None:
        if session_id == "next":
            writer.session_message(session_id, writer.stream_object({"text": "ready"}))
            return
        try:
            while True:
                writer.session_message(
                    session_id, writer.stream_object({"text": "running"})
                )
                gevent.sleep(0.01)
        finally:
            finalized.set()

    server.handler = execute
    connection = HTTPConnection("127.0.0.1", http.server_port, timeout=2)
    requests = []
    try:
        for session_id in ("cancelled", "next"):
            connection.request(
                "POST",
                "/invoke",
                body=json.dumps({
                    "event": "request",
                    "session_id": session_id,
                    "data": {},
                }),
                headers={"Content-Type": "application/json"},
            )
            request = reader.request_queue.get(timeout=2)
            requests.append(request)
            future = server.executer.submit(
                server._execute_request_in_thread,
                request.session_id,
                request.data,
                reader,
                request.writer,
            )
            response = connection.getresponse()
            if session_id == "cancelled":
                assert b"running" in response.readline()
                assert connection.sock is not None
                connection.sock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                )
                response.close()
                connection.close()
                assert finalized.wait(timeout=2)
                future.result(timeout=2)
            else:
                messages = [
                    json.loads(line)["data"]
                    for line in response.read().splitlines()
                    if line
                ]
                assert [message["type"] for message in messages] == ["stream", "end"]
                assert messages[0]["data"] == {"text": "ready"}
                future.result(timeout=2)
    finally:
        connection.close()
        for request in requests:
            request.writer.close()
        http.stop(timeout=2)
        server.executer.shutdown(wait=True)
