from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FilePublicEvent(CatalogSlackEvent):
    """Slack event handler for `file.public`."""

    EVENT_KEY = "file_public"
