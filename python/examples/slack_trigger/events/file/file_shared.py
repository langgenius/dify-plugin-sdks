from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileSharedEvent(CatalogSlackEvent):
    """Slack event handler for `file.shared`."""

    EVENT_KEY = "file_shared"
