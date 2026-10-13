# ruff: file-ignore[import-private-name]

from collections.abc import Generator
from unittest.mock import Mock

import gevent
import pytest
from gevent.event import Event

from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.server.__base.filter_reader import FilterReader
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter


class MemoryReader(RequestReader):
    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        yield from ()


def message(reader: RequestReader, session: str, request: str) -> PluginInStream:
    return PluginInStream(
        session_id=session,
        event=PluginInStreamEvent.BackwardInvocationResponse,
        data={"backwards_request_id": request},
        reader=reader,
        writer=StdioResponseWriter(),
    )


def test_request_reader_routes_interleaved_responses_to_matching_subscribers() -> None:
    reader = MemoryReader()
    responses = [
        message(reader, session, request)
        for session, request in [("a", "1"), ("b", "1"), ("a", "2"), ("b", "2")]
    ]
    subscribers = [
        reader.read(
            lambda item, expected=item: (
                (item.session_id, item.data) == (expected.session_id, expected.data)
            )
        )
        for item in responses
    ]
    observer = reader.read(lambda _item: True)
    unrelated = reader.read(lambda item: item.event == PluginInStreamEvent.Request)

    for item in reversed(responses):
        reader._process_line(item)
    reader.close()

    assert [list(subscriber.read()) for subscriber in subscribers] == [
        [item] for item in responses
    ]
    assert list(observer.read()) == list(reversed(responses))
    assert list(unrelated.read()) == []
    assert reader.readers == []


def test_bad_filter_or_subscriber_does_not_prevent_other_delivery(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    reader = MemoryReader()
    bad_filter = Mock(side_effect=ValueError("bad filter"))
    reader.read(bad_filter)
    failing_writer = reader.read(lambda _item: True)
    monkeypatch.setattr(
        failing_writer, "write", Mock(side_effect=ValueError("bad subscriber"))
    )
    healthy = reader.read(lambda _item: True)
    item = message(reader, "session", "request")

    reader._process_line(item)
    reader.close()

    assert list(healthy.read()) == [item]
    assert "bad filter" in caplog.text
    assert "bad subscriber" in caplog.text


def test_subscriber_can_close_and_register_during_filtering() -> None:
    reader = MemoryReader()
    created: list[FilterReader] = []

    def replace(_item: PluginInStream) -> bool:
        original.close()
        created.append(reader.read(lambda _item: True))
        return True

    original = reader.read(replace)
    first, second = (
        message(reader, "session", "first"),
        message(reader, "session", "second"),
    )
    task = gevent.spawn(reader._process_line, first)
    try:
        task.get(timeout=1)
        reader._process_line(second)
        reader.close()

        assert list(original.read()) == []
        assert list(created[0].read()) == [second]
    finally:
        reader.close()
        task.kill()


def test_close_while_filter_is_pending_prevents_late_delivery() -> None:
    reader = MemoryReader()
    entered, resume = Event(), Event()

    def wait_for_close(_item: PluginInStream) -> bool:
        entered.set()
        assert resume.wait(timeout=1)
        return True

    subscriber = reader.read(wait_for_close)
    task = gevent.spawn(reader._process_line, message(reader, "session", "request"))
    try:
        assert entered.wait(timeout=1)
        subscriber.close()
        resume.set()
        task.get(timeout=1)

        assert list(subscriber.read()) == []
        assert subscriber.queue.empty()
    finally:
        resume.set()
        reader.close()
        task.kill()


def test_close_wakes_blocked_subscriber_and_is_idempotent() -> None:
    reader = MemoryReader()
    subscriber = reader.read(lambda _item: True)
    task = gevent.spawn(lambda: list(subscriber.read()))
    try:
        gevent.sleep(0)
        assert not task.ready()
        reader.close()
        reader.close()

        assert task.get(timeout=1) == []
        assert reader.readers == []
        replacement = reader.read(lambda _item: True)
        item = message(reader, "session", "after-close")
        reader._process_line(item)
        assert next(replacement.read(timeout_for_round=0)) == item
    finally:
        reader.close()
        task.kill()


def test_filter_reader_timeout_does_not_end_the_subscription() -> None:
    reader = MemoryReader()
    subscriber = reader.read(lambda _item: True)
    stream = subscriber.read(timeout_for_round=0)
    item = message(reader, "session", "request")

    assert next(stream) is None
    reader._process_line(item)
    assert next(stream) == item
    assert next(stream) is None
    subscriber.close()
    assert list(stream) == []


def test_filter_reader_context_closes_after_consumer_error() -> None:
    reader = MemoryReader()
    subscriber = reader.read(lambda _item: True)

    error = ValueError("consumer failed")
    with pytest.raises(ValueError, match="consumer failed"), subscriber:
        raise error

    assert reader.readers == []
    assert list(subscriber.read()) == []


def test_filter_reader_drains_queued_data_once_after_close() -> None:
    subscriber = FilterReader(lambda _item: True)
    item = message(MemoryReader(), "session", "request")
    subscriber.write(item)
    subscriber.close()

    assert list(subscriber.read()) == [item]
    assert list(subscriber.read()) == []
    subscriber.write(item)
    assert list(subscriber.read()) == []


def test_filter_reader_notifies_waiter_when_close_callback_fails() -> None:
    subscriber = FilterReader(
        lambda _item: True, Mock(side_effect=ValueError("close failed"))
    )

    with pytest.raises(ValueError, match="close failed"):
        subscriber.close()

    task = gevent.spawn(lambda: list(subscriber.read()))
    try:
        assert task.get(timeout=1) == []
        subscriber.close()
    finally:
        task.kill()


def test_event_loop_restarts_when_a_reader_returns_batches() -> None:
    class BatchedReader(MemoryReader):
        calls = 0

        def _read_stream(self) -> Generator[PluginInStream, None, None]:
            self.calls += 1
            if self.calls <= 2:
                yield message(self, "session", str(self.calls))
            else:
                self.close()

    reader = BatchedReader()
    subscriber = reader.read(lambda _item: True)
    loop = gevent.spawn(reader.event_loop)
    try:
        loop.get(timeout=1)
        assert [item.data["backwards_request_id"] for item in subscriber.read()] == [
            "1",
            "2",
        ]
        assert reader.readers == []
    finally:
        reader.close()
        loop.kill()


def test_event_loop_recovers_from_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = MemoryReader()
    subscriber = reader.read(lambda _item: True)
    item = message(reader, "session", "request")
    attempts = iter([OSError("temporary read error"), item])

    def read_stream() -> Generator[PluginInStream, None, None]:
        result = next(attempts)
        if isinstance(result, OSError):
            raise result
        yield result
        reader.close()

    monkeypatch.setattr(reader, "_read_stream", read_stream)
    loop = gevent.spawn(reader.event_loop)
    try:
        loop.get(timeout=1)
        assert list(subscriber.read()) == [item]
        assert reader.readers == []
    finally:
        reader.close()
        loop.kill()


def test_event_loop_stops_delivering_buffered_data_after_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = MemoryReader()
    subscriber = reader.read(lambda _item: True)
    first = message(reader, "session", "first")

    def read_stream() -> Generator[PluginInStream, None, None]:
        yield first
        reader.close()
        yield message(reader, "session", "after-close")

    monkeypatch.setattr(reader, "_read_stream", read_stream)
    reader.event_loop()

    assert list(subscriber.read()) == [first]
