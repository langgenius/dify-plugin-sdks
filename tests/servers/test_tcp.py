import json
import threading
from unittest.mock import Mock

import pytest

from dify_plugin.core.entities.plugin.io import PluginInStreamEvent
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter


def _make_reader() -> TCPReaderWriter:
    reader = object.__new__(TCPReaderWriter)
    reader.host = "localhost"
    reader.port = 5000
    reader.reconnect_attempts = 1
    reader.reconnect_timeout = 0
    reader.alive = True
    reader._closed = False
    reader.sock = Mock()
    reader.opt_lock = threading.Lock()
    reader._state_lock = threading.Lock()
    reader._connect_lock = threading.Lock()
    return reader


def test_tcp_reconnect_discards_partial_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = _make_reader()
    reader.reconnect_attempts = 2
    reader.sock.close.side_effect = OSError("close failed")

    payload = {
        "session_id": "new-session",
        "event": PluginInStreamEvent.Request.value,
        "data": {},
    }
    chunks: list[bytes | Exception] = [
        b'{"session_id":"old',
        ConnectionError("disconnected"),
        json.dumps(payload).encode() + b"\n",
    ]

    monkeypatch.setattr(reader, "_receive_available", Mock(side_effect=chunks))

    connect = Mock()

    def reconnect() -> None:
        if connect.call_count <= reader.reconnect_attempts:
            msg = "connect failed"
            raise OSError(msg)
        reader.alive = True

    connect.side_effect = reconnect
    monkeypatch.setattr(reader, "_connect", connect)

    assert next(reader._read_stream()).session_id == "new-session"
    assert connect.call_count == 3
    reader.sock.close.assert_called_once_with()


def test_tcp_put_sends_complete_frame() -> None:
    reader = _make_reader()

    reader.heartbeat()

    reader.sock.sendall.assert_called_once()
    payload = reader.sock.sendall.call_args.args[0]
    assert payload.endswith(b"\n\n")
    assert json.loads(payload) == {"event": "heartbeat", "session_id": None, "data": {}}


def test_tcp_write_closes_and_reraises_send_failure() -> None:
    reader = _make_reader()
    send_error = OSError("send failed")
    reader.sock.sendall.side_effect = send_error
    reader.sock.close.side_effect = OSError
    reader.launch = Mock()

    with pytest.raises(OSError, match="send failed") as exc_info:
        reader.write("payload")

    assert exc_info.value is send_error
    reader.sock.close.assert_called_once_with()
    reader.launch.assert_not_called()


def test_tcp_old_write_failure_does_not_close_new_socket() -> None:
    reader = _make_reader()
    old_sock = reader.sock
    new_sock = Mock()
    send_error = OSError("old connection failed")

    def replace_connection(_data: bytes) -> None:
        reader.sock = new_sock
        reader.alive = True
        raise send_error

    old_sock.sendall.side_effect = replace_connection

    with pytest.raises(OSError, match="old connection failed"):
        reader.write("payload")

    old_sock.close.assert_called_once_with()
    new_sock.close.assert_not_called()
    assert reader.alive


def test_tcp_concurrent_launch_connects_once() -> None:
    reader = _make_reader()
    reader.alive = False
    connect_started = threading.Event()
    release_connect = threading.Event()

    def connect() -> None:
        connect_started.set()
        release_connect.wait(timeout=1)
        with reader._state_lock:
            reader.alive = True

    reader._connect = Mock(side_effect=connect)
    first = threading.Thread(target=reader.launch, daemon=True)
    second = threading.Thread(target=reader.launch, daemon=True)

    first.start()
    assert connect_started.wait(timeout=1)
    second.start()
    release_connect.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    reader._connect.assert_called_once_with()


def test_tcp_close_stops_reconnecting(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = _make_reader()
    reader._connect = Mock()
    reader._receive_available = Mock(side_effect=ConnectionError("disconnected"))
    reader.sock.close.side_effect = OSError("close failed")
    monkeypatch.setattr(
        "dify_plugin.core.server.tcp.request_reader.time.sleep",
        lambda _timeout: reader.close(),
    )

    with pytest.raises(StopIteration):
        next(reader._read_stream())

    reader._connect.assert_not_called()
    assert reader.sock.close.call_count == 2


def test_tcp_reconnect_does_not_hide_callback_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _make_reader()
    reader._connect = Mock(side_effect=ValueError("invalid declaration"))
    reader._receive_available = Mock(side_effect=ConnectionError("disconnected"))
    monkeypatch.setattr(
        "dify_plugin.core.server.tcp.request_reader.time.sleep",
        Mock(side_effect=[None, AssertionError("callback error was swallowed")]),
    )

    with pytest.raises(ValueError, match="invalid declaration"):
        next(reader._read_stream())


def test_tcp_reader_reconnects_after_writer_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _make_reader()
    payload = {
        "session_id": "reconnected",
        "event": PluginInStreamEvent.Request.value,
        "data": {},
    }
    responses = iter([None, json.dumps(payload).encode() + b"\n"])

    def receive(_sock: object) -> bytes | None:
        data = next(responses)
        if data is None:
            reader.alive = False
        return data

    reader._receive_available = Mock(side_effect=receive)
    reader._connect = Mock(side_effect=lambda: setattr(reader, "alive", True))
    monkeypatch.setattr(
        "dify_plugin.core.server.tcp.request_reader.time.sleep",
        lambda _timeout: None,
    )

    assert next(reader._read_stream()).session_id == "reconnected"
    reader._connect.assert_called_once_with()
