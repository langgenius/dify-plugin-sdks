from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelUnarchiveEvent(CatalogSlackEvent):
    """Slack event handler for `channel.unarchive`."""

    EVENT_KEY = "channel_unarchive"
