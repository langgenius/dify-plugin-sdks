import json
import os
from itertools import chain

import gevent
import pytest

from dify_plugin.core.entities.plugin.io import PluginInStreamEvent
from dify_plugin.core.server.stdio import request_reader as stdio_module
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader


@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
@pytest.mark.parametrize("event", ["request", "backwards_response"])
def test_stdio_preserves_frames_and_metadata(
    monkeypatch: pytest.MonkeyPatch, chunk_size: int, event: str
) -> None:
    # daemon session_manager.Session.Message supplies these fields to both transports.
    payload = {
        "session_id": "session-1",
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "app_id": "app-1",
        "endpoint_id": "endpoint-1",
        "context": {"credentials": {"tool": {"provider": "credential-1"}}},
        "data": {"text": "你好 🌍\nsecond line", "sequence": 1},
        "event": event,
    }
    second = {**payload, "session_id": "session-2", "data": {"sequence": 2}}
    wire = b" \n" + json.dumps(payload, ensure_ascii=False).encode() + b"\r\n\n"
    wire += json.dumps(second).encode() + b"\n"
    chunks = iter(
        chain(
            (wire[i : i + chunk_size] for i in range(0, len(wire), chunk_size)), [b""]
        )
    )
    reader = StdioRequestReader()
    monkeypatch.setattr(reader, "_read_async", lambda: next(chunks))

    messages = list(reader._read_stream())

    assert len(messages) == 2
    for message, expected in zip(messages, [payload, second], strict=True):
        assert message.event == PluginInStreamEvent(event)
        assert message.reader is reader
        assert {
            field: getattr(message, field) for field in expected if field != "event"
        } == {field: value for field, value in expected.items() if field != "event"}


@pytest.mark.parametrize(
    "invalid",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"session_id":"s","event":"unknown","data":{}}',
        b"\xff",
    ],
)
def test_stdio_reports_invalid_frame_and_reads_the_next_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invalid: bytes,
) -> None:
    payload = {"session_id": "valid", "event": "request", "data": {"ok": True}}
    chunks = iter([invalid + b"\n" + json.dumps(payload).encode() + b"\n", b""])
    reader = StdioRequestReader()
    monkeypatch.setattr(reader, "_read_async", lambda: next(chunks))

    messages = list(reader._read_stream())

    assert [(message.session_id, message.data) for message in messages] == [
        ("valid", {"ok": True})
    ]
    errors = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    assert len(errors) == 1
    assert errors[0]["event"] == "error"
    assert errors[0]["data"]["error"]


@pytest.mark.parametrize(
    "optional_fields", [{}, {"context": None, "conversation_id": None}]
)
def test_stdio_accepts_absent_optional_metadata(
    monkeypatch: pytest.MonkeyPatch, optional_fields: dict[str, None]
) -> None:
    payload = {
        "session_id": "session",
        "event": "request",
        "data": {},
        **optional_fields,
    }
    chunks = iter([json.dumps(payload).encode() + b"\n", b""])
    reader = StdioRequestReader()
    monkeypatch.setattr(reader, "_read_async", lambda: next(chunks))

    (message,) = reader._read_stream()

    assert message.context is None
    assert message.conversation_id is None
    assert message.message_id is None
    assert message.app_id is None
    assert message.endpoint_id is None


def test_stdio_reads_frame_larger_than_the_read_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "大" * 350_000
    payload = {"session_id": "large", "event": "request", "data": {"text": text}}
    wire = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
    chunks = iter(
        chain((wire[i : i + 65536] for i in range(0, len(wire), 65536)), [b""])
    )
    reader = StdioRequestReader()
    monkeypatch.setattr(reader, "_read_async", lambda: next(chunks))

    (message,) = reader._read_stream()

    assert message.data == {"text": text}


def test_stdio_eof_closes_subscribers_and_discards_incomplete_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"session_id": "complete", "event": "request", "data": {}}
    chunks = iter([json.dumps(payload).encode() + b'\n{"session_id":"unfinished"', b""])
    reader = StdioRequestReader()
    monkeypatch.setattr(reader, "_read_async", lambda: next(chunks))
    subscriber = reader.read(lambda _message: True)
    loop = gevent.spawn(reader.event_loop)
    try:
        loop.get(timeout=1)
        assert [message.session_id for message in subscriber.read()] == ["complete"]
        assert reader.readers == []
    finally:
        reader.close()
        loop.kill()


def test_stdio_reads_actual_pipe_until_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    read_fd, write_fd = os.pipe()
    payload = {"session_id": "pipe", "event": "request", "data": {"text": "管道"}}
    wire = json.dumps(payload, ensure_ascii=False).encode() + b"\n"

    def produce() -> None:
        with os.fdopen(write_fd, "wb", buffering=0) as pipe:
            for byte in wire:
                pipe.write(bytes([byte]))

    reader = StdioRequestReader()
    with os.fdopen(read_fd, "rb", buffering=0) as pipe:
        monkeypatch.setattr(stdio_module.sys, "stdin", pipe)
        producer = gevent.spawn(produce)
        consumer = gevent.spawn(lambda: list(reader._read_stream()))
        try:
            messages = consumer.get(timeout=2)
            producer.get(timeout=2)
            assert [(message.session_id, message.data) for message in messages] == [
                ("pipe", payload["data"])
            ]
        finally:
            reader.close()
            producer.kill()
            consumer.kill()


def test_closed_stdio_reader_does_not_resume_processing() -> None:
    reader = StdioRequestReader()
    reader.close()

    reader.event_loop()

    assert list(reader._read_stream()) == []
    subscriber = reader.read(lambda _message: True)
    reader.close()
    assert list(subscriber.read()) == []
