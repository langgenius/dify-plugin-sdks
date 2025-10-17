from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupUnarchiveEvent(CatalogSlackEvent):
    """Slack event handler for `group.unarchive`."""

    EVENT_KEY = "group_unarchive"
