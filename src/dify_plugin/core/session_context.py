"""
Request-scoped session context for model plugins.

Model plugins (LLM, Embedding, Rerank, etc.) do not receive the Session
object through their ``_invoke()`` signature — unlike tool plugins which
get it via their constructor.  This module bridges that gap by storing
the current Session in a :class:`~contextvars.ContextVar` so that model
plugin code can retrieve it on demand via :func:`get_current_session`.

Usage in a custom model plugin::

    from dify_plugin.core.session_context import get_current_session

    class MyLLM(LargeLanguageModel):
        def _invoke(self, model, credentials, prompt_messages, ...):
            session = get_current_session()
            if session and session.app_id:
                # tag the request with the originating Dify app
                ...

Note on ``app_id`` being ``None``:

    ``session.app_id`` is ``None`` when the model is invoked outside of
    an app execution context — for example, RAG routing, conversation
    title generation, or suggested question generation.  These calls
    represent shared infrastructure costs not attributable to a specific
    app.

    When building provider-side cost dashboards, the recommended
    approach is:

    * If ``app_id`` is not ``None``, tag the request with it for
      per-app cost attribution.
    * If ``app_id`` is ``None``, either skip tagging or use a
      sentinel value such as ``"dify_system"`` to bucket these
      calls separately from external (non-Dify) traffic.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dify_plugin.core.runtime import Session

_current_session: ContextVar[Session | None] = ContextVar(
    "_current_session", default=None
)


def get_current_session() -> Session | None:
    """Return the :class:`Session` for the current model invocation, or
    ``None`` when called outside of a plugin dispatch context.

    Returns:
        The current session, or ``None``.
    """
    return _current_session.get()
