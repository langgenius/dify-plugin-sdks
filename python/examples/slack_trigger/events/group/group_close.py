from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupCloseEvent(CatalogSlackEvent):
    """Slack event handler for `group.close`."""

    EVENT_KEY = "group_close"
