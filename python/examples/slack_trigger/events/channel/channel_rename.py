from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ChannelRenameEvent(CatalogSlackEvent):
    """Slack event handler for `channel.rename`."""

    EVENT_KEY = "channel_rename"
