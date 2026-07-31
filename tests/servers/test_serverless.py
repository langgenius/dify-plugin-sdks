from collections.abc import Generator
from queue import Empty
from unittest.mock import Mock

import pytest

from dify_plugin.core.server.serverless import request_reader as serverless_module
from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader


def _handle_request(
    reader: ServerlessRequestReader,
) -> tuple[Generator[str, None, None], int]:
    with reader.app.test_request_context(
        json={"event": "request", "session_id": "session", "data": {}},
    ):
        response, status = reader.handler()

    assert not isinstance(response, str)
    return response, status


def test_serverless_response_stops_after_sentinel() -> None:
    reader = ServerlessRequestReader()
    response, status = _handle_request(reader)
    plugin_in = reader.request_queue.get_nowait()
    plugin_in.writer.write("chunk")
    plugin_in.writer.done()

    assert status == 200
    assert list(response) == ["chunk"]


def test_serverless_enqueue_error_returns_explicit_500() -> None:
    reader = ServerlessRequestReader()
    reader.request_queue = Mock()
    reader.request_queue.put.side_effect = RuntimeError("enqueue failed")

    with reader.app.test_request_context(
        json={"event": "request", "session_id": "session", "data": {}},
    ):
        response, status = reader.handler()

    assert response == "enqueue failed"
    assert status == 500


def test_serverless_timeout_preserves_wall_clock_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = ServerlessRequestReader(max_single_connection_lifetime=100)
    queue = Mock()
    queue.get.side_effect = Empty
    monkeypatch.setattr(serverless_module, "Queue", Mock(return_value=queue))
    response, _ = _handle_request(reader)
    monkeypatch.setattr(
        serverless_module,
        "time",
        Mock(time=Mock(side_effect=[0, 101])),
    )

    assert list(response) == []
    queue.get.assert_called_once_with(timeout=1)
