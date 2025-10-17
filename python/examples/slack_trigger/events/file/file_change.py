from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileChangeEvent(CatalogSlackEvent):
    """Slack event handler for `file.change`."""

    EVENT_KEY = "file_change"
