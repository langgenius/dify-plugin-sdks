from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileCreatedEvent(CatalogSlackEvent):
    """Slack event handler for `file.created`."""

    EVENT_KEY = "file_created"
