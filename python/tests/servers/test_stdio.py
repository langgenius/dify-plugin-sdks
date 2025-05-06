import json

from dify_plugin.core.entities.plugin.io import PluginInStreamEvent
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader


def test_stdio(monkeypatch):
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
    dataflow_bytes = b"".join([json.dumps(payload).encode("utf-8") + b"\n" for _ in range(200)])
    # split dataflow_bytes into 64KB chunks
    dataflow_chunks = [dataflow_bytes[i : i + 65536] for i in range(0, len(dataflow_bytes), 65536)]

    def mock_read_async():
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


def test_stdio_with_empty_line(monkeypatch):
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
    dataflow_bytes = b"".join([json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)])
    dataflow_bytes += b"\n"
    dataflow_bytes += b"".join([json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)])
    dataflow_bytes += b"\n"
    dataflow_bytes += b"".join([json.dumps(payload).encode("utf-8") + b"\n" for _ in range(100)])
    dataflow_bytes += b"\n"

    def mock_read_async():
        return dataflow_bytes

    monkeypatch.setattr(reader, "_read_async", mock_read_async)

    iters = 0
    for line in reader._read_stream():
        assert line.event == PluginInStreamEvent.Request
        iters += 1
        if iters == 300:
            break

    assert iters == 300
