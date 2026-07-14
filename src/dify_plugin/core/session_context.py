"""Current model invocation session access."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dify_plugin.core.runtime import Session

_current_session: ContextVar[Session | None] = ContextVar(
    "dify_plugin_current_session",
    default=None,
)


def get_current_session() -> Session | None:
    """Return the current model invocation session, if any.

    Model plugins can read ``session.app_id`` from the returned session.
    It is ``None`` for model calls outside an app execution context.

    Returns:
        The current session, or ``None``.
    """
    return _current_session.get()


@contextmanager
def use_current_session(session: Session) -> Iterator[None]:
    token = _current_session.set(session)
    try:
        yield
    finally:
        _current_session.reset(token)
