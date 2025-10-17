from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageImEvent(CatalogSlackEvent):
    """Slack event handler for `message.im`."""

    EVENT_KEY = "message_im"
