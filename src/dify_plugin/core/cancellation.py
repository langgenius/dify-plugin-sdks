"""Abort an in-flight request when the caller abandons it.

The request body runs on a child greenlet spawned by the pooled worker, and only that
child is ever killed. The pool's own greenlets are therefore out of the blast radius:
killing one while it sits idle in ``work_queue.get()`` would retire it permanently,
because ``_worker`` does not catch ``BaseException``.

``RequestCancelledError`` derives from ``BaseException`` deliberately: an
``Exception``-derived cancel is swallowed by ordinary ``except Exception`` in provider
code, and a ``GreenletExit``-derived one is reported by gevent as success. It is added
to the hub's ``NOT_ERROR`` so a routine cancel prints no traceback.

Two windows must not receive an asynchronous raise. While a frame is being written the
raise would truncate it -- on the shared debug socket that corrupts a line for
every session, not just this one -- so writers wrap each frame in ``uninterruptible()``
and the cancel is deferred to the end of it. And once the body has finished there is
nothing left to cancel, so the entry is settled under the same lock the canceller takes.
"""

import contextvars
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock

import gevent
from gevent.hub import Hub

from dify_plugin.core.gevent_runtime import interruptible

logger = logging.getLogger(__name__)


class RequestCancelledError(BaseException):
    """Raised inside a request once the caller has abandoned it."""


# A routine cancel is not a crash; keep gevent from reporting one.
if RequestCancelledError not in Hub.NOT_ERROR:
    Hub.NOT_ERROR = (*Hub.NOT_ERROR, RequestCancelledError)

_current_entry: contextvars.ContextVar["_Entry | None"] = contextvars.ContextVar(
    "dify_plugin_cancellation_entry", default=None
)


@dataclass
class _Entry:
    """The cancellable state of one request."""

    session_id: str
    lock: Lock = field(default_factory=Lock)
    cancelled: bool = False
    settled: bool = False
    greenlet: gevent.Greenlet | None = None
    guard_depth: int = 0
    deferred: bool = False


@contextmanager
def uninterruptible() -> Iterator[None]:
    """Hold off a cancel for the duration of the block, then deliver it.

    A cancel raised part way through a frame leaves a truncated line on the wire, so
    every frame write runs inside one of these.

    Raises:
        RequestCancelledError: if a cancel arrived while the block was running.
    """
    entry = _current_entry.get()
    if entry is None:
        yield
        return

    with entry.lock:
        entry.guard_depth += 1

    completed = False
    try:
        yield
        completed = True
    finally:
        with entry.lock:
            entry.guard_depth -= 1
            due = entry.deferred and entry.guard_depth == 0 and completed
            if due:
                entry.deferred = False

    if due:
        raise RequestCancelledError(entry.session_id)


class CancellationRegistry:
    """Maps a session id to the request currently running under it."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, _Entry] = {}

    def register(self, session_id: str) -> _Entry | None:
        """Claim a session id, or return None if one is already in flight under it."""
        entry = _Entry(session_id=session_id)
        with self._lock:
            if session_id in self._entries:
                logger.warning(
                    "Session %s is already in flight; it will not be cancellable.",
                    session_id,
                )
                return None
            self._entries[session_id] = entry
        return entry

    def discard(self, entry: _Entry | None) -> None:
        """Settle the request and drop it, so a later cancel cannot reach it."""
        if entry is None:
            return
        with entry.lock:
            entry.settled = True
            entry.greenlet = None
        with self._lock:
            if self._entries.get(entry.session_id) is entry:
                del self._entries[entry.session_id]

    def cancel(self, session_id: str) -> bool:
        """Abort the request running under ``session_id``, if there still is one."""
        with self._lock:
            entry = self._entries.get(session_id)
        if entry is None:
            return False

        with entry.lock:
            if entry.cancelled or entry.settled:
                return False
            entry.cancelled = True
            if entry.greenlet is None:
                # Still queued, or not yet attached: the body aborts before it starts.
                return True
            if entry.guard_depth:
                entry.deferred = True
                return True
            target = entry.greenlet

        target.kill(RequestCancelledError(session_id), block=False)
        return True

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def _attach(entry: _Entry) -> None:
    """Become the kill target, unless a cancel already landed."""
    with entry.lock:
        if entry.cancelled:
            raise RequestCancelledError(entry.session_id)
        entry.greenlet = gevent.getcurrent()


def _child_main(
    entry: _Entry,
    fn: Callable[..., object],
    args: tuple[object, ...],
) -> BaseException | None:
    """Run the body, returning whatever it died of rather than raising."""
    token = _current_entry.set(entry)
    try:
        _attach(entry)
        fn(*args)
    except BaseException as e:
        return e
    finally:
        _current_entry.reset(token)
    return None


def run_cancellable(
    entry: _Entry | None,
    fn: Callable[..., object],
    *args: object,
) -> None:
    """Run ``fn`` on a child greenlet so a cancel can interrupt it."""
    if entry is None or not interruptible():
        fn(*args)
        return

    child = gevent.spawn(contextvars.copy_context().run, _child_main, entry, fn, args)
    try:
        failure = child.get()
    finally:
        if not child.dead:
            # The supervisor is unwinding; do not leave the body running headless.
            child.kill(block=False)

    if failure is None:
        return
    if isinstance(failure, RequestCancelledError):
        # Re-raise a fresh one: the original's traceback pins the child's frames, and
        # with them any generator it left suspended.
        del failure
        raise RequestCancelledError(entry.session_id) from None
    raise failure
