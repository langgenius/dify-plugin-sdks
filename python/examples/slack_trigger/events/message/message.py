from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageEvent(CatalogSlackEvent):
    """Slack event handler for `message`."""

    EVENT_KEY = "message"
