from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelDeletedEvent(CatalogSlackEvent):
    """Slack event handler for `channel.deleted`."""

    EVENT_KEY = "channel_deleted"
