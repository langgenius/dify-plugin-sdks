import json
from collections.abc import Generator

import gevent
import gevent.event
import pytest

from dify_plugin.core import cancellation
from dify_plugin.core.cancellation import (
    CancellationRegistry,
    RequestCancelledError,
    run_cancellable,
    uninterruptible,
)
from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter

SESSION = "session-1"
TOLERANCE = 1.0


class YieldingWriter(StdioResponseWriter):
    """A writer that switches greenlets mid-frame, like a socket under backpressure."""

    def __init__(self) -> None:
        self.buffer = ""

    def write(self, data: str) -> None:
        gevent.sleep(0)
        self.buffer += data
        gevent.sleep(0)

    def done(self) -> None:
        pass

    def frames(self) -> list[str]:
        return [chunk for chunk in self.buffer.split("\n\n") if chunk.strip()]


def run_in_greenlet(registry: CancellationRegistry, body: object) -> gevent.Greenlet:
    entry = registry.register(SESSION)

    def supervisor() -> None:
        try:
            run_cancellable(entry, body)
        finally:
            registry.discard(entry)

    return gevent.spawn(supervisor)


def test_a_blocked_body_is_cancelled_and_its_cleanup_runs() -> None:
    registry = CancellationRegistry()
    cleaned: list[str] = []
    started = gevent.event.Event()

    def body() -> None:
        try:
            started.set()
            gevent.sleep(30)
        finally:
            cleaned.append("released")

    worker = run_in_greenlet(registry, body)
    assert started.wait(timeout=TOLERANCE)
    assert registry.cancel(SESSION) is True
    worker.join(timeout=TOLERANCE)

    assert isinstance(worker.exception, RequestCancelledError)
    assert cleaned == ["released"]


def test_a_cancel_that_lands_before_the_body_starts_stops_it_running() -> None:
    registry = CancellationRegistry()
    ran: list[str] = []
    entry = registry.register(SESSION)
    assert registry.cancel(SESSION) is True

    with pytest.raises(RequestCancelledError):
        run_cancellable(entry, lambda: ran.append("body"))

    assert ran == []


def test_a_cancel_after_the_request_settled_is_a_no_op() -> None:
    registry = CancellationRegistry()
    worker = run_in_greenlet(registry, lambda: None)
    worker.join(timeout=TOLERANCE)

    assert registry.cancel(SESSION) is False
    assert worker.successful()


def test_a_second_cancel_is_a_no_op_so_it_cannot_abort_the_first_unwind() -> None:
    registry = CancellationRegistry()
    worker = run_in_greenlet(registry, lambda: gevent.sleep(30))
    gevent.sleep(0)

    assert registry.cancel(SESSION) is True
    assert registry.cancel(SESSION) is False
    worker.join(timeout=TOLERANCE)


def test_a_cancel_for_an_unknown_session_is_a_no_op() -> None:
    assert CancellationRegistry().cancel("nobody") is False


def test_a_duplicate_session_id_is_refused_rather_than_clobbering() -> None:
    registry = CancellationRegistry()
    first = registry.register(SESSION)

    assert first is not None
    assert registry.register(SESSION) is None


def test_a_settled_request_is_dropped_from_the_registry() -> None:
    registry = CancellationRegistry()
    worker = run_in_greenlet(registry, lambda: None)
    worker.join(timeout=TOLERANCE)

    assert registry.cancel(SESSION) is False
    assert registry._entries == {}


def test_a_cancel_never_truncates_a_frame_on_the_wire() -> None:
    """A half-written frame corrupts a line for every session on a shared connection."""
    registry = CancellationRegistry()
    writer = YieldingWriter()

    def body() -> None:
        for i in range(50):
            writer.session_message(session_id=SESSION, data={"type": "stream", "i": i})

    worker = run_in_greenlet(registry, body)
    gevent.sleep(0)
    gevent.sleep(0)
    registry.cancel(SESSION)
    worker.join(timeout=TOLERANCE)

    assert isinstance(worker.exception, RequestCancelledError)
    assert writer.frames(), "expected the cancel to land mid-stream, not before it"
    for frame in writer.frames():
        json.loads(frame)


def test_the_deferred_cancel_still_arrives_once_the_frame_is_out() -> None:
    registry = CancellationRegistry()
    entry = registry.register(SESSION)
    assert entry is not None
    reached: list[str] = []

    def body() -> None:
        with uninterruptible():
            registry.cancel(SESSION)
            reached.append("frame written")
        reached.append("should not get here")

    with pytest.raises(RequestCancelledError):
        run_cancellable(entry, body)

    assert reached == ["frame written"]


def test_the_pool_is_never_the_kill_target() -> None:
    """Killing a pooled worker would retire it; only the per-request child may die."""
    registry = CancellationRegistry()
    worker = run_in_greenlet(registry, lambda: gevent.sleep(30))
    gevent.sleep(0)
    registry.cancel(SESSION)
    worker.join(timeout=TOLERANCE)

    survivor = run_in_greenlet(CancellationRegistry(), lambda: None)
    survivor.join(timeout=TOLERANCE)
    assert survivor.successful()


def test_a_routine_cancel_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    registry = CancellationRegistry()
    worker = run_in_greenlet(registry, lambda: gevent.sleep(30))
    gevent.sleep(0)
    registry.cancel(SESSION)
    worker.join(timeout=TOLERANCE)
    gevent.sleep(0)

    assert not capsys.readouterr().err


def test_the_body_runs_inline_when_it_cannot_be_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail open, exactly as the first-token deadline does."""
    monkeypatch.setattr(cancellation, "interruptible", lambda: False)
    registry = CancellationRegistry()
    ran: list[str] = []

    run_cancellable(registry.register(SESSION), lambda: ran.append("body"))

    assert ran == ["body"]


def test_a_cancelled_request_does_not_leak_its_side_channel_reader() -> None:
    """A suspended generator's `with` never exits, so the session must close it."""
    session = Session.empty_session()
    before = len(session.reader.readers)

    def never_matches(_: object) -> bool:
        return False

    def body() -> Generator[None, None, None]:
        with session.open_reader(never_matches):
            yield
            yield

    suspended = body()
    next(suspended)
    assert len(session.reader.readers) == before + 1

    session.close()

    assert len(session.reader.readers) == before
