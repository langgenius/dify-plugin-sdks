import json
from collections.abc import Callable, Generator
from unittest.mock import Mock

import pytest

from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader


class FiniteStdioRequestReader(StdioRequestReader):
    def __init__(self) -> None:
        super().__init__()
        self.stream_calls = 0

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        self.stream_calls += 1
        if self.stream_calls > 1:
            raise SystemExit
        yield from ()


class LegacyLock:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def acquire(self) -> None:
        self.calls.append("acquire")

    def release(self) -> None:
        self.calls.append("release")


class ClosingGuard:
    def __init__(self, close: Callable[[], None]) -> None:
        self.close = close

    def __bool__(self) -> bool:
        return True

    def __del__(self) -> None:
        self.close()


def test_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "session_id": "1",
        "conversation_id": "2",
        "message_id": "3",
        "app_id": "4",
        "endpoint_id": "5",
        "data": {"test": "test" * 1000},
        "event": PluginInStreamEvent.Request.value,
    }

    reader = StdioRequestReader()
    dataflow_bytes = b"".join([
        json.dumps(payload).encode("utf-8") + b"\n" for _ in range(200)
    ])
    # split dataflow_bytes into 64KB chunks
    dataflow_chunks = [
        dataflow_bytes[i : i + 65536] for i in range(0, len(dataflow_bytes), 65536)
    ]

    def mock_read_async() -> bytes:
        return dataflow_chunks.pop(0)

    # mock reader._read_async
    monkeypatch.setattr(reader, "_read_async", mock_read_async)

    iters = 0

    for line in reader._read_stream():
        assert line.event == PluginInStreamEvent.Request
        assert line.session_id == "1"
        assert line.conversation_id == "2"
        assert line.message_id == "3"
        assert line.app_id == "4"
        assert line.endpoint_id == "5"
        iters += 1
        if iters == 200:
            break

    assert iters == 200


def test_stdio_with_empty_line(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "session_id": "1",
        "conversation_id": "2",
        "message_id": "3",
        "app_id": "4",
        "endpoint_id": "5",
        "data": {"test": "test" * 1000},
        "event": PluginInStreamEvent.Request.value,
    }

    reader = StdioRequestReader()
    dataflow_bytes = b"".join([
        json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)
    ])
    dataflow_bytes += b"\n"
    dataflow_bytes += b"".join([
        json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)
    ])
    dataflow_bytes += b"\n"
    dataflow_bytes += b"".join([
        json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)
    ])
    dataflow_bytes += b"\n"

    def mock_read_async() -> bytes:
        return dataflow_bytes

    monkeypatch.setattr(reader, "_read_async", mock_read_async)

    iters = 0
    for line in reader._read_stream():
        assert line.event == PluginInStreamEvent.Request
        iters += 1
        if iters == 300:
            break

    assert iters == 300


def test_event_loop_does_not_throttle_finite_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep = Mock()
    monkeypatch.setattr(
        "dify_plugin.core.server.__base.request_reader.time.sleep",
        sleep,
    )

    with pytest.raises(SystemExit):
        FiniteStdioRequestReader().event_loop()

    sleep.assert_not_called()


def test_request_reader_preserves_acquire_release_lock_protocol() -> None:
    reader = StdioRequestReader()
    lock = LegacyLock()
    reader.lock = lock

    filtered_reader = reader.read(lambda _data: True)
    filtered_reader.close()
    reader.close()

    assert lock.calls == [
        "acquire",
        "release",
        "acquire",
        "release",
        "acquire",
        "release",
    ]


def test_request_reader_keeps_filter_result_alive_through_write() -> None:
    reader = StdioRequestReader()
    filtered_reader = reader.read(
        lambda _data: ClosingGuard(filtered_reader.close),
    )
    data = Mock()

    reader._process_line(data)

    assert list(filtered_reader.read()) == [data]
