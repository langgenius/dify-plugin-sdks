import threading
from unittest.mock import Mock

import pytest

from dify_plugin.core.server.tcp import request_reader as tcp_module
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter


def _make_reader() -> TCPReaderWriter:
    reader = object.__new__(TCPReaderWriter)
    reader.alive = True
    reader.sock = Mock()
    reader.sock.send.return_value = len(b"payload")
    reader.opt_lock = threading.Lock()
    return reader


def test_tcp_write_keeps_legacy_hook_locking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _make_reader()
    monkeypatch.setattr(
        tcp_module.gevent_socket,
        "socket",
        tcp_module.native_socket.socket,
    )

    writer = threading.Thread(target=reader.write, args=("payload",), daemon=True)
    writer.start()
    writer.join(timeout=1)

    assert not writer.is_alive()
    reader.sock.send.assert_called_once_with(b"payload")


def test_tcp_protected_launch_still_connects() -> None:
    reader = _make_reader()
    reader.reconnect_attempts = 1
    reader.reconnect_timeout = 0
    reader._connect = Mock()

    reader._launch()

    reader._connect.assert_called_once_with()
