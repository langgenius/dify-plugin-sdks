from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ScopeGrantedEvent(CatalogSlackEvent):
    """Slack event handler for `scope.granted`."""

    EVENT_KEY = "scope_granted"
