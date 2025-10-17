from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageGroupsEvent(CatalogSlackEvent):
    """Slack event handler for `message.groups`."""

    EVENT_KEY = "message_groups"
