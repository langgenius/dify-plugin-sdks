from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageChannelsEvent(CatalogSlackEvent):
    """Slack event handler for `message.channels`."""

    EVENT_KEY = "message_channels"
