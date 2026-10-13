import json
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from queue import Queue
from threading import Barrier

import gevent
import pytest
from pydantic import BaseModel

from dify_plugin.core.server.serverless.response_writer import ServerlessResponseWriter
from tests.servers.helpers import RecordingResponseWriter


class Payload(BaseModel):
    text: str


@pytest.mark.parametrize("data", [b"bytes\n\n", "text\n\n"])
def test_serverless_writer_preserves_bytes_and_text(data: bytes | str) -> None:
    queue = Queue()
    writer = ServerlessResponseWriter(queue)
    writer.write(data)
    writer.done()
    assert queue.get_nowait() == data
    assert queue.get_nowait() is None


@pytest.mark.parametrize("method", ["stream", "error", "invoke", "end"])
def test_session_frames_match_daemon_protocol(method: str) -> None:
    writer = RecordingResponseWriter()
    payload = Payload(text="你好\nsecond line")
    factories = {
        "stream": writer.stream_object,
        "error": writer.stream_error_object,
        "invoke": writer.stream_invoke_object,
    }
    message = (
        writer.stream_end_object() if method == "end" else factories[method](payload)
    )

    writer.session_message("session-1", message)

    wire = "".join(writer.writes)
    assert wire.endswith("\n\n")
    assert wire.count("\n") == 2
    assert writer.messages == [
        {
            "event": "session",
            "session_id": "session-1",
            "data": {
                "type": method,
                "data": {} if method == "end" else {"text": payload.text},
            },
        }
    ]
    assert writer.session_message_text("session-1", message) == wire


@pytest.mark.parametrize(
    ("method", "event", "session_id", "payload"),
    [
        ("log", "log", None, {"level": "info", "message": "ready"}),
        ("error", "error", "session-1", {"error": "invalid request"}),
        ("heartbeat", "heartbeat", None, {}),
    ],
)
def test_control_frames(
    method: str, event: str, session_id: str | None, payload: dict
) -> None:
    writer = RecordingResponseWriter()
    if method == "heartbeat":
        writer.heartbeat()
    elif method == "error":
        writer.error(session_id=session_id, data=payload)
    else:
        writer.log(payload)

    assert writer.messages == [
        {"event": event, "session_id": session_id, "data": payload}
    ]
    assert "".join(writer.writes).endswith("\n\n")


def test_concurrent_sessions_produce_complete_frames() -> None:
    class YieldingResponseWriter(RecordingResponseWriter):
        def write(self, data: str) -> None:
            super().write(data)
            # Let senders awakened by the entry barrier reach the writer.
            gevent.sleep(0.001)

    writer = YieldingResponseWriter()
    ready = Barrier(2)

    def send(session_id: str) -> None:
        ready.wait(timeout=2)
        writer.session_message(session_id, {"text": session_id})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(send, session_id) for session_id in ("one", "two")]
        for future in futures:
            future.result(timeout=2)

    frames = "".join(writer.writes).split("\n\n")
    assert not frames[-1]
    assert sorted(
        (json.loads(frame) for frame in frames[:-1]),
        key=itemgetter("session_id"),
    ) == [
        {"event": "session", "session_id": session_id, "data": {"text": session_id}}
        for session_id in ("one", "two")
    ]
