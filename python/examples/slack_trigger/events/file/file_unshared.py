from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileUnsharedEvent(CatalogSlackEvent):
    """Slack event handler for `file.unshared`."""

    EVENT_KEY = "file_unshared"
