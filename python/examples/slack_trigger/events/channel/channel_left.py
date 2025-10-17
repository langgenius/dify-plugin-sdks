from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelLeftEvent(CatalogSlackEvent):
    """Slack event handler for `channel.left`."""

    EVENT_KEY = "channel_left"
