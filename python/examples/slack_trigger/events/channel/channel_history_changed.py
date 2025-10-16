from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelHistoryChangedEvent(CatalogSlackEvent):
    """Slack event handler for `channel.history.changed`."""

    EVENT_KEY = "channel_history_changed"
