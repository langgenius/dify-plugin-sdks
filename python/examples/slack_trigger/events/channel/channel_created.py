from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelCreatedEvent(CatalogSlackEvent):
    """Slack event handler for `channel.created`."""

    EVENT_KEY = "channel_created"
