from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ScopeDeniedEvent(CatalogSlackEvent):
    """Slack event handler for `scope.denied`."""

    EVENT_KEY = "scope_denied"
