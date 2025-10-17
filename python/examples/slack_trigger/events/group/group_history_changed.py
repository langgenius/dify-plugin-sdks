from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupHistoryChangedEvent(CatalogSlackEvent):
    """Slack event handler for `group.history.changed`."""

    EVENT_KEY = "group_history_changed"
