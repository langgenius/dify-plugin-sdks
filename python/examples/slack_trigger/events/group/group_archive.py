from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupArchiveEvent(CatalogSlackEvent):
    """Slack event handler for `group.archive`."""

    EVENT_KEY = "group_archive"
