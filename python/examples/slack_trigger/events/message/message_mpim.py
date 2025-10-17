from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageMpimEvent(CatalogSlackEvent):
    """Slack event handler for `message.mpim`."""

    EVENT_KEY = "message_mpim"
