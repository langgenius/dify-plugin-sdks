from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupLeftEvent(CatalogSlackEvent):
    """Slack event handler for `group.left`."""

    EVENT_KEY = "group_left"
