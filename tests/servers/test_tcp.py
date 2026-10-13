import errno
import json
import signal
from collections.abc import Generator
from unittest.mock import Mock

import gevent
import pytest
from gevent import socket
from gevent.event import Event

from dify_plugin.core.entities.plugin.io import PluginInStreamEvent
from dify_plugin.core.server.tcp import request_reader as tcp_module
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter


@pytest.fixture
def tcp_reader() -> Generator[TCPReaderWriter, None, None]:
    previous_sigint = signal.getsignal(signal.SIGINT)
    reader = TCPReaderWriter(
        "127.0.0.1", 0, "test-key", reconnect_attempts=2, reconnect_timeout=0
    )
    try:
        yield reader
    finally:
        reader.close()
        signal.signal(signal.SIGINT, previous_sigint)


@pytest.fixture
def connected(
    tcp_reader: TCPReaderWriter,
) -> Generator[tuple[TCPReaderWriter, socket.socket], None, None]:
    client, peer = socket.socketpair()
    client.settimeout(2)
    peer.settimeout(2)
    tcp_reader.sock = client
    tcp_reader.alive = True
    try:
        yield tcp_reader, peer
    finally:
        peer.close()
        client.close()


@pytest.fixture
def listener(tcp_reader: TCPReaderWriter) -> Generator[socket.socket, None, None]:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(2)
        tcp_reader.port = server.getsockname()[1]
        yield server


def test_tcp_sends_handshake_before_registration(
    tcp_reader: TCPReaderWriter, listener: socket.socket
) -> None:
    tcp_reader.on_connected = lambda: tcp_reader.write('{"type":"end","data":{}}\n\n')

    tcp_reader.launch()

    peer, _address = listener.accept()
    with peer, peer.makefile("rb") as stream:
        peer.settimeout(2)
        assert json.loads(stream.readline()) == {
            "type": "handshake",
            "data": {"key": "test-key"},
        }
        assert json.loads(stream.readline()) == {"type": "end", "data": {}}
        assert stream.readline() == b"\n"


def test_tcp_retries_transient_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
    tcp_reader: TCPReaderWriter,
    listener: socket.socket,
) -> None:
    create_connection = tcp_module.gevent_socket.create_connection
    attempts = 0

    def connect(address: tuple[str, int]) -> socket.socket:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            msg = "not ready"
            raise ConnectionRefusedError(msg)
        return create_connection(address)

    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    tcp_reader.launch()

    peer, _address = listener.accept()
    with peer, peer.makefile("rb") as stream:
        peer.settimeout(2)
        assert json.loads(stream.readline()) == {
            "type": "handshake",
            "data": {"key": "test-key"},
        }
    assert attempts == 2


def test_tcp_exhausted_connection_attempts_raise(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    connect = Mock(side_effect=ConnectionRefusedError("not ready"))
    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)

    with pytest.raises(ConnectionRefusedError, match="not ready"):
        tcp_reader.launch()

    assert connect.call_count == tcp_reader.reconnect_attempts
    assert not tcp_reader.alive


def test_tcp_failed_handshake_closes_each_connection(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    clients = []
    for _ in range(tcp_reader.reconnect_attempts):
        client, peer = socket.socketpair()
        peer.close()
        clients.append(client)
    connect = Mock(side_effect=clients)
    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    try:
        with pytest.raises(BrokenPipeError):
            tcp_reader.launch()

        assert not tcp_reader.alive
        assert all(client.fileno() == -1 for client in clients)
    finally:
        for client in clients:
            client.close()


@pytest.mark.parametrize("chunk_size", [1, 7, 1048576])
@pytest.mark.parametrize("event", ["request", "backwards_response"])
def test_tcp_preserves_frames_metadata_and_split_utf8(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    connected: tuple[TCPReaderWriter, socket.socket],
    chunk_size: int,
    event: str,
) -> None:
    reader, peer = connected
    payload = {
        "session_id": "session-1",
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "app_id": "app-1",
        "endpoint_id": "endpoint-1",
        "context": {"trace": "trace-1"},
        "event": event,
        "data": {"text": "你好 🌍\nsecond line"},
    }
    second = {**payload, "session_id": "session-2", "data": {"sequence": 2}}
    wire = b"\n" + json.dumps(payload, ensure_ascii=False).encode() + b"\r\n \n"
    wire += json.dumps(second).encode() + b"\n"
    monkeypatch.setattr(
        reader, "_recv_from_sock", lambda size: reader.sock.recv(min(size, chunk_size))
    )
    peer.sendall(wire)
    stream = reader._read_stream()
    try:
        messages = [next(stream), next(stream)]
        for message, expected in zip(messages, [payload, second], strict=True):
            assert message.event == PluginInStreamEvent(event)
            assert message.reader is reader
            assert message.writer is reader
            assert {
                field: getattr(message, field) for field in expected if field != "event"
            } == {field: value for field, value in expected.items() if field != "event"}
        assert "An error occurred while parsing" not in caplog.text
    finally:
        stream.close()


def test_tcp_recovers_from_invalid_frames(
    caplog: pytest.LogCaptureFixture, connected: tuple[TCPReaderWriter, socket.socket]
) -> None:
    reader, peer = connected
    malformed = [
        b"not-json",
        b"[]",
        b"{}",
        b'{"session_id":"s","event":"unknown","data":{}}',
        b"\xff",
    ]
    payload = {"session_id": "valid", "event": "request", "data": {"ok": True}}
    peer.sendall(b"\n".join([*malformed, json.dumps(payload).encode(), b""]))
    stream = reader._read_stream()
    try:
        message = next(stream)
        assert message.session_id == "valid"
        assert message.data == {"ok": True}
        assert message.context is None
        assert message.conversation_id is None
        assert caplog.text.count("An error occurred while parsing") == len(malformed)
    finally:
        stream.close()


def test_tcp_reads_frame_larger_than_socket_buffer(
    connected: tuple[TCPReaderWriter, socket.socket],
) -> None:
    reader, peer = connected
    text = "大" * 350_000
    wire = (
        json.dumps(
            {"session_id": "large", "event": "request", "data": {"text": text}},
            ensure_ascii=False,
        ).encode()
        + b"\n"
    )
    producer = gevent.spawn(peer.sendall, wire)
    stream = reader._read_stream()
    try:
        message = next(stream)
        producer.get(timeout=2)
        assert message.data == {"text": text}
    finally:
        stream.close()
        producer.kill()


def test_tcp_idle_read_can_be_followed_by_data(
    monkeypatch: pytest.MonkeyPatch,
    connected: tuple[TCPReaderWriter, socket.socket],
) -> None:
    reader, peer = connected
    idle = Event()
    read_data = reader._read_data

    def observe_idle_read() -> bytes | None:
        data = read_data()
        if data is None:
            idle.set()
        return data

    def respond() -> None:
        assert idle.wait(timeout=2)
        peer.sendall(b'{"session_id":"after-idle","event":"request","data":{}}\n')

    monkeypatch.setattr(reader, "_read_data", observe_idle_read)
    producer = gevent.spawn(respond)
    stream = reader._read_stream()
    consumer = gevent.spawn(next, stream)
    try:
        message = consumer.get(timeout=3)
        producer.get(timeout=2)
        assert message.session_id == "after-idle"
        assert message.data == {}
    finally:
        consumer.kill()
        producer.kill()
        stream.close()


@pytest.mark.parametrize("error_number", [errno.EAGAIN, errno.EBADF])
def test_tcp_read_handles_only_retryable_socket_errors(
    monkeypatch: pytest.MonkeyPatch,
    connected: tuple[TCPReaderWriter, socket.socket],
    error_number: int,
) -> None:
    reader, peer = connected
    peer.sendall(b"data")
    monkeypatch.setattr(
        reader,
        "_recv_from_sock",
        Mock(side_effect=BlockingIOError(error_number, "read failed")),
    )

    if error_number == errno.EAGAIN:
        assert reader._read_data() is None
    else:
        with pytest.raises(BlockingIOError) as error:
            reader._read_data()
        assert error.value.errno == error_number


def test_tcp_reconnect_discards_partial_frame_from_previous_connection(
    tcp_reader: TCPReaderWriter, listener: socket.socket
) -> None:
    tcp_reader.launch()
    old_socket = tcp_reader.sock
    first_peer, _address = listener.accept()
    with first_peer, first_peer.makefile("rb") as stream:
        assert json.loads(stream.readline())["type"] == "handshake"
        first_peer.sendall(b'{"session_id":"old-partial')
    release_peer = Event()

    def respond_after_reconnect() -> None:
        second_peer, _address = listener.accept()
        with second_peer, second_peer.makefile("rb") as stream:
            second_peer.settimeout(2)
            assert json.loads(stream.readline())["type"] == "handshake"
            for session in ["first-after-reconnect", "second-after-reconnect"]:
                second_peer.sendall(
                    json.dumps({
                        "session_id": session,
                        "event": "request",
                        "data": {},
                    }).encode()
                    + b"\n"
                )
            assert release_peer.wait(timeout=2)

    producer = gevent.spawn(respond_after_reconnect)
    stream = tcp_reader._read_stream()
    consumer = gevent.spawn(next, stream)
    try:
        message = consumer.get(timeout=2)
        assert message.session_id == "first-after-reconnect"
        assert old_socket.fileno() == -1
    finally:
        release_peer.set()
        try:
            producer.get(timeout=2)
        finally:
            consumer.kill()
            producer.kill()
            stream.close()
            old_socket.close()


def test_tcp_close_wakes_reader_and_subscribers_without_reconnecting(
    connected: tuple[TCPReaderWriter, socket.socket],
) -> None:
    reader, _peer = connected
    subscriber = reader.read(lambda _item: True)
    consumer = gevent.spawn(lambda: list(reader._read_stream()))
    waiter = gevent.spawn(lambda: list(subscriber.read()))
    try:
        gevent.sleep(0)
        assert not consumer.ready()
        assert not waiter.ready()
        reader.close()
        reader.close()

        assert consumer.get(timeout=2) == []
        assert waiter.get(timeout=2) == []
        assert reader.readers == []
    finally:
        reader.close()
        consumer.kill()
        waiter.kill()


def test_tcp_close_during_reconnect_delay_stops_retry(
    monkeypatch: pytest.MonkeyPatch, connected: tuple[TCPReaderWriter, socket.socket]
) -> None:
    reader, peer = connected
    peer.close()
    monkeypatch.setattr(tcp_module.time, "sleep", lambda _delay: reader.close())

    assert list(reader._read_stream()) == []


def test_tcp_concurrent_partial_writes_keep_complete_payloads(
    monkeypatch: pytest.MonkeyPatch, connected: tuple[TCPReaderWriter, socket.socket]
) -> None:
    reader, peer = connected
    send = reader._write_to_sock
    blocked = False

    def send_part(data: bytes) -> int:
        nonlocal blocked
        if not blocked:
            blocked = True
            raise BlockingIOError(errno.EAGAIN, "try again")
        sent = send(data[:3])
        gevent.sleep(0)
        return sent

    monkeypatch.setattr(reader, "_write_to_sock", send_part)
    payloads = ["first 你好\n", "second 🌍\n"]
    writers = [gevent.spawn(reader.write, payload) for payload in payloads]
    try:
        for writer in writers:
            writer.get(timeout=2)
        received = bytearray()
        expected_size = sum(len(payload.encode()) for payload in payloads)
        while len(received) < expected_size:
            received.extend(peer.recv(expected_size - len(received)))
        assert bytes(received) in {
            "".join(payloads).encode(),
            "".join(reversed(payloads)).encode(),
        }
    finally:
        for writer in writers:
            writer.kill()


def test_tcp_zero_byte_send_reconnects(
    monkeypatch: pytest.MonkeyPatch, connected: tuple[TCPReaderWriter, socket.socket]
) -> None:
    reader, _peer = connected
    monkeypatch.setattr(
        reader,
        "_write_to_sock",
        Mock(side_effect=[0, AssertionError("retried zero-byte send")]),
    )
    monkeypatch.setattr(reader, "_launch", Mock())

    assert reader.write("payload") is None
    reader._launch.assert_called_once_with()


@pytest.mark.parametrize(
    "write_error",
    [
        BrokenPipeError(errno.EPIPE, "write failed"),
        BlockingIOError(errno.EBADF, "write failed"),
    ],
    ids=["broken-pipe", "nonretryable-blocking-error"],
)
def test_tcp_write_failure_returns_after_successful_reconnect(
    monkeypatch: pytest.MonkeyPatch,
    tcp_reader: TCPReaderWriter,
    listener: socket.socket,
    write_error: OSError,
) -> None:
    tcp_reader.launch()
    old_socket = tcp_reader.sock
    first_peer, _address = listener.accept()
    send = tcp_reader._write_to_sock
    try:
        monkeypatch.setattr(
            tcp_reader,
            "_write_to_sock",
            Mock(side_effect=write_error),
        )
        assert tcp_reader.write("unsent payload\n") is None
        assert old_socket.fileno() == -1
        monkeypatch.setattr(tcp_reader, "_write_to_sock", send)
        second_peer, _address = listener.accept()
        with second_peer, second_peer.makefile("rb") as stream:
            second_peer.settimeout(2)
            assert json.loads(stream.readline())["type"] == "handshake"
            tcp_reader.write("next payload\n")
            assert stream.readline() == b"next payload\n"
    finally:
        first_peer.close()
        old_socket.close()


@pytest.mark.parametrize("cancellation", ["kill", "timeout"])
@pytest.mark.parametrize("daemon_available", [False, True])
@pytest.mark.parametrize("pending_read", ["idle", "error"])
def test_cancelled_partial_write_closes_connection_and_preserves_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    tcp_reader: TCPReaderWriter,
    listener: socket.socket,
    cancellation: str,
    daemon_available: bool,
    pending_read: str,
) -> None:
    tcp_reader.launch()
    old_socket = tcp_reader.sock
    first_peer, _address = listener.accept()
    first_peer.settimeout(1)
    sent_prefix, resume = Event(), Event()
    read_entered, resume_read = Event(), Event()
    reconnect_entered, resume_reconnect = Event(), Event()
    send = tcp_reader._write_to_sock
    read_data = tcp_reader._read_data
    connect = tcp_module.gevent_socket.create_connection
    error = gevent.GreenletExit() if cancellation == "kill" else gevent.Timeout(0.05)
    first_read = True
    attempts = 0

    def read() -> bytes | None:
        nonlocal first_read
        if first_read:
            first_read = False
            read_entered.set()
            assert resume_read.wait(timeout=2)
            if pending_read == "idle":
                return None
        return read_data()

    def reconnect(address: tuple[str, int]) -> socket.socket:
        nonlocal attempts
        attempts += 1
        reconnect_entered.set()
        assert resume_reconnect.wait(timeout=2)
        return connect(address)

    def send_part(data: bytes) -> int:
        sent = send(data[:3])
        sent_prefix.set()
        resume.wait()
        return sent

    def write() -> BaseException:
        try:
            if isinstance(error, gevent.Timeout):
                with error:
                    tcp_reader.write('{"interrupted":true}\n')
            else:
                tcp_reader.write('{"interrupted":true}\n')
        except BaseException as caught:
            return caught
        pytest.fail("cancelled write completed")

    monkeypatch.setattr(tcp_reader, "_write_to_sock", send_part)
    monkeypatch.setattr(tcp_reader, "_read_data", read)
    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", reconnect)
    subscriber = tcp_reader.read(lambda _message: True)
    loop = gevent.spawn(tcp_reader.event_loop)
    task = None
    try:
        assert read_entered.wait(timeout=1)
        task = gevent.spawn(write)
        assert sent_prefix.wait(timeout=1)
        if not daemon_available:
            listener.close()
        if cancellation == "kill":
            task.kill(exception=error, block=False)
        assert task.get(timeout=1) is error
        assert old_socket.fileno() == -1
        assert not reconnect_entered.is_set()
        with first_peer.makefile("rb") as stream:
            assert json.loads(stream.readline())["type"] == "handshake"
            assert stream.read() == b'{"i'

        resume_read.set()
        assert reconnect_entered.wait(timeout=1)
        resume_reconnect.set()
        if not daemon_available:
            loop.get(timeout=1)
            assert not tcp_reader.alive
            assert attempts == tcp_reader.reconnect_attempts
            assert list(subscriber.read()) == []
            return

        monkeypatch.setattr(tcp_reader, "_write_to_sock", send)
        second_peer, _address = listener.accept()
        with second_peer, second_peer.makefile("rb") as stream:
            second_peer.settimeout(1)
            assert json.loads(stream.readline())["type"] == "handshake"
            second_peer.sendall(
                b'{"session_id":"recovered","event":"request","data":{}}\n'
            )
            message = next(subscriber.read(timeout_for_round=1))
            assert message is not None
            assert message.session_id == "recovered"
            tcp_reader.write('{"next":true}\n')
            assert json.loads(stream.readline()) == {"next": True}
            tcp_reader.close()
            loop.get(timeout=2)
    finally:
        resume.set()
        resume_read.set()
        resume_reconnect.set()
        if task is not None:
            task.kill(block=True, timeout=1)
        tcp_reader.close()
        loop.kill(block=True, timeout=1)
        first_peer.close()
        old_socket.close()


def test_tcp_write_without_connection_fails(tcp_reader: TCPReaderWriter) -> None:
    with pytest.raises(Exception, match="connection is dead"):
        tcp_reader.write("payload")


def test_tcp_close_during_write_reports_error_without_reconnecting(
    monkeypatch: pytest.MonkeyPatch, connected: tuple[TCPReaderWriter, socket.socket]
) -> None:
    reader, _peer = connected
    entered, resume = Event(), Event()
    send = reader._write_to_sock

    def wait_for_close(data: bytes) -> int:
        entered.set()
        assert resume.wait(timeout=1)
        return send(data)

    monkeypatch.setattr(reader, "_write_to_sock", wait_for_close)
    writer = gevent.spawn(reader.write, "pending payload")
    try:
        assert entered.wait(timeout=1)
        reader.close()
        resume.set()

        with pytest.raises(OSError, match="Bad file descriptor") as error:
            writer.get(timeout=1)
        assert error.value.errno == errno.EBADF
        assert not reader.alive
        assert reader.sock.fileno() == -1
    finally:
        resume.set()
        writer.kill()


@pytest.mark.parametrize("close_first", [False, True])
def test_explicit_launch_reopens_or_replaces_connection(
    tcp_reader: TCPReaderWriter, listener: socket.socket, close_first: bool
) -> None:
    tcp_reader.launch()
    first_socket = tcp_reader.sock
    first_peer, _address = listener.accept()
    with first_peer:
        if close_first:
            tcp_reader.close()
        tcp_reader.launch()
        assert tcp_reader.alive
        assert first_socket.fileno() == -1
        second_peer, _address = listener.accept()
        with second_peer, second_peer.makefile("rb") as stream:
            second_peer.settimeout(1)
            assert json.loads(stream.readline())["type"] == "handshake"
            tcp_reader.write("after launch\n")
            assert stream.readline() == b"after launch\n"


def test_registration_write_failure_respects_connection_attempt_limit(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    connections: list[tuple[socket.socket, socket.socket]] = []

    def connect(_address: tuple[str, int]) -> socket.socket:
        if len(connections) >= tcp_reader.reconnect_attempts:
            pytest.fail("registration failure exceeded the connection attempt limit")
        pair = socket.socketpair()
        connections.append(pair)
        return pair[0]

    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    monkeypatch.setattr(
        tcp_reader,
        "_write_to_sock",
        Mock(side_effect=BrokenPipeError("registration failed")),
    )
    tcp_reader.on_connected = lambda: tcp_reader.write("registration\n")
    try:
        with pytest.raises(BrokenPipeError, match="registration failed"):
            tcp_reader.launch()
        assert len(connections) == tcp_reader.reconnect_attempts
        assert not tcp_reader.alive
        assert all(client.fileno() == -1 for client, _peer in connections)
        for _client, peer in connections:
            peer.settimeout(1)
            assert json.loads(peer.recv(1024)) == {
                "type": "handshake",
                "data": {"key": "test-key"},
            }
    finally:
        for client, peer in connections:
            client.close()
            peer.close()


def test_close_while_connecting_discards_late_connection(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    entered, resume = Event(), Event()
    client, peer = socket.socketpair()
    callback = Mock()

    def connect(_address: tuple[str, int]) -> socket.socket:
        entered.set()
        assert resume.wait(timeout=1)
        return client

    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    tcp_reader.on_connected = callback
    task = gevent.spawn(tcp_reader.launch)
    try:
        assert entered.wait(timeout=1)
        tcp_reader.close()
        resume.set()
        task.get(timeout=1)

        assert not tcp_reader.alive
        assert client.fileno() == -1
        callback.assert_not_called()
        peer.settimeout(1)
        assert peer.recv(1024) == b""
    finally:
        resume.set()
        task.kill()
        client.close()
        peer.close()


def test_read_loop_survives_idle_read_during_write_reconnection(
    monkeypatch: pytest.MonkeyPatch,
    connected: tuple[TCPReaderWriter, socket.socket],
) -> None:
    reader, _peer = connected
    read_entered, connecting, resume_connect, idle_returned = (
        Event(),
        Event(),
        Event(),
        Event(),
    )
    replacement, replacement_peer = socket.socketpair()
    read_data = reader._read_data
    first_read = True
    subscriber = reader.read(lambda _message: True)

    def read() -> bytes | None:
        nonlocal first_read
        if first_read:
            first_read = False
            read_entered.set()
            assert connecting.wait(timeout=1)
            idle_returned.set()
            return None
        return read_data()

    def connect(_address: tuple[str, int]) -> socket.socket:
        connecting.set()
        assert resume_connect.wait(timeout=1)
        return replacement

    monkeypatch.setattr(reader, "_read_data", read)
    monkeypatch.setattr(
        reader, "_write_to_sock", Mock(side_effect=BrokenPipeError("write failed"))
    )
    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    loop = gevent.spawn(reader.event_loop)
    writer = None
    response = None
    try:
        assert read_entered.wait(timeout=1)
        writer = gevent.spawn(reader.write, "failed payload")
        assert idle_returned.wait(timeout=1)
        gevent.sleep(0)
        assert not loop.ready()
        assert not reader._closed
        resume_connect.set()
        assert writer.get(timeout=1) is None
        replacement_peer.sendall(
            b'{"session_id":"new-connection","event":"request","data":{}}\n'
        )
        response = gevent.spawn(next, subscriber.read())
        assert response.get(timeout=1).session_id == "new-connection"
        reader.close()
        loop.get(timeout=2)
    finally:
        resume_connect.set()
        if writer is not None:
            writer.kill()
        if response is not None:
            response.kill()
        reader.close()
        loop.kill()
        replacement.close()
        replacement_peer.close()


@pytest.mark.parametrize("stale_result", [OSError("old read failed"), b"still partial"])
def test_stale_read_cannot_close_or_corrupt_replacement_connection(
    monkeypatch: pytest.MonkeyPatch,
    connected: tuple[TCPReaderWriter, socket.socket],
    stale_result: OSError | bytes,
) -> None:
    reader, _peer = connected
    pending_read, resume_read = Event(), Event()
    replacement, replacement_peer = socket.socketpair()
    read_data = reader._read_data
    reads = 0

    def read() -> bytes | None:
        nonlocal reads
        reads += 1
        if reads == 1:
            return b'{"session_id":"old-partial'
        if reads == 2:
            pending_read.set()
            assert resume_read.wait(timeout=1)
            if isinstance(stale_result, OSError):
                raise stale_result
            return stale_result
        return read_data()

    connect = Mock(side_effect=[replacement])
    monkeypatch.setattr(reader, "_read_data", read)
    monkeypatch.setattr(
        reader, "_write_to_sock", Mock(side_effect=BrokenPipeError("write failed"))
    )
    monkeypatch.setattr(tcp_module.gevent_socket, "create_connection", connect)
    stream = reader._read_stream()
    consumer = gevent.spawn(next, stream)
    try:
        assert pending_read.wait(timeout=1)
        assert reader.write("failed payload") is None
        replacement_peer.sendall(
            b'{"session_id":"first-after-reconnect","event":"request","data":{}}\n'
            b'{"session_id":"second-after-reconnect","event":"request","data":{}}\n'
        )
        resume_read.set()

        assert consumer.get(timeout=1).session_id == "first-after-reconnect"
        assert reader.alive
        assert connect.call_count == 1
    finally:
        resume_read.set()
        consumer.kill()
        stream.close()
        reader.close()
        replacement.close()
        replacement_peer.close()


def test_regular_write_waits_until_registration_finishes(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    registration_started, resume_registration, write_started = Event(), Event(), Event()
    client, peer = socket.socketpair()
    peer.settimeout(1)

    def register() -> None:
        tcp_reader.write("first registration\n")
        registration_started.set()
        assert resume_registration.wait(timeout=1)
        tcp_reader.write("last registration\n")

    def write() -> None:
        write_started.set()
        tcp_reader.write("ordinary frame\n")

    monkeypatch.setattr(
        tcp_module.gevent_socket, "create_connection", lambda _address: client
    )
    tcp_reader.on_connected = register
    connection = gevent.spawn(tcp_reader.launch)
    writer = None
    try:
        assert registration_started.wait(timeout=1)
        writer = gevent.spawn(write)
        assert write_started.wait(timeout=1)
        resume_registration.set()
        connection.get(timeout=1)
        writer.get(timeout=1)

        with peer.makefile("rb") as stream:
            assert json.loads(stream.readline())["type"] == "handshake"
            assert [stream.readline() for _ in range(3)] == [
                b"first registration\n",
                b"last registration\n",
                b"ordinary frame\n",
            ]
    finally:
        resume_registration.set()
        connection.kill()
        if writer is not None:
            writer.kill()
        client.close()
        peer.close()


def test_connection_recovers_from_one_registration_write_failure(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    first_client, first_peer = socket.socketpair()
    second_client, second_peer = socket.socketpair()
    second_peer.settimeout(1)
    first_write = True
    send = tcp_reader._write_to_sock

    def fail_first_write(data: bytes) -> int:
        nonlocal first_write
        if first_write:
            first_write = False
            msg = "first registration failed"
            raise BrokenPipeError(msg)
        return send(data)

    monkeypatch.setattr(
        tcp_module.gevent_socket,
        "create_connection",
        Mock(side_effect=[first_client, second_client]),
    )
    monkeypatch.setattr(tcp_reader, "_write_to_sock", fail_first_write)
    tcp_reader.on_connected = lambda: tcp_reader.write("registration\n")
    try:
        tcp_reader.launch()
        tcp_reader.write("ordinary frame\n")

        assert first_client.fileno() == -1
        assert tcp_reader.alive
        with second_peer.makefile("rb") as stream:
            assert json.loads(stream.readline())["type"] == "handshake"
            assert stream.readline() == b"registration\n"
            assert stream.readline() == b"ordinary frame\n"
    finally:
        first_client.close()
        first_peer.close()
        second_client.close()
        second_peer.close()


def test_cancelled_registration_closes_connection(
    monkeypatch: pytest.MonkeyPatch, tcp_reader: TCPReaderWriter
) -> None:
    registered, resume = Event(), Event()
    client, peer = socket.socketpair()

    def register() -> None:
        registered.set()
        resume.wait()

    monkeypatch.setattr(
        tcp_module.gevent_socket, "create_connection", lambda _address: client
    )
    tcp_reader.on_connected = register
    task = gevent.spawn(tcp_reader.launch)
    try:
        assert registered.wait(timeout=1)
        task.kill(block=True, timeout=1)
        task.get(timeout=1)

        assert not tcp_reader.alive
        assert client.fileno() == -1
        with pytest.raises(Exception, match="connection is dead"):
            tcp_reader.write("ordinary frame\n")
    finally:
        resume.set()
        task.kill()
        client.close()
        peer.close()


def test_read_reconnection_waits_for_complete_pending_write(
    monkeypatch: pytest.MonkeyPatch,
    connected: tuple[TCPReaderWriter, socket.socket],
) -> None:
    reader, old_peer = connected
    sent_prefix, resume_write, read_failed = Event(), Event(), Event()
    replacement, replacement_peer = socket.socketpair()
    replacement_peer.settimeout(1)
    payload = b"complete old payload\n"
    send = reader._write_to_sock
    read_data = reader._read_data
    first_write = True

    def send_part(data: bytes) -> int:
        nonlocal first_write
        if first_write:
            first_write = False
            sent = send(data[:3])
            sent_prefix.set()
            assert resume_write.wait(timeout=1)
            return sent
        return send(data)

    def read() -> bytes | None:
        try:
            return read_data()
        except Exception:
            read_failed.set()
            raise

    monkeypatch.setattr(reader, "_write_to_sock", send_part)
    monkeypatch.setattr(reader, "_read_data", read)
    monkeypatch.setattr(
        tcp_module.gevent_socket, "create_connection", Mock(side_effect=[replacement])
    )
    replacement_peer.sendall(
        b'{"session_id":"replacement","event":"request","data":{}}\n'
    )
    writer = gevent.spawn(reader.write, payload.decode())
    stream = reader._read_stream()
    consumer = None
    try:
        assert sent_prefix.wait(timeout=1)
        old_peer.shutdown(socket.SHUT_WR)
        consumer = gevent.spawn(next, stream)
        assert read_failed.wait(timeout=1)
        resume_write.set()
        writer.get(timeout=1)
        assert consumer.get(timeout=1).session_id == "replacement"

        with old_peer.makefile("rb") as old_stream:
            assert old_stream.read() == payload
        reader.close()
        with replacement_peer.makefile("rb") as new_stream:
            assert json.loads(new_stream.readline())["type"] == "handshake"
            assert new_stream.read() == b""
    finally:
        resume_write.set()
        writer.kill()
        if consumer is not None:
            consumer.kill()
        stream.close()
        reader.close()
        replacement.close()
        replacement_peer.close()
