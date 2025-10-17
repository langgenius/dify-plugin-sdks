from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupOpenEvent(CatalogSlackEvent):
    """Slack event handler for `group.open`."""

    EVENT_KEY = "group_open"
