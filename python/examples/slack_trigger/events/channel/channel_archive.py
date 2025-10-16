from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelArchiveEvent(CatalogSlackEvent):
    """Slack event handler for `channel.archive`."""

    EVENT_KEY = "channel_archive"
