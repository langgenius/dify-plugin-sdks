from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileDeletedEvent(CatalogSlackEvent):
    """Slack event handler for `file.deleted`."""

    EVENT_KEY = "file_deleted"
