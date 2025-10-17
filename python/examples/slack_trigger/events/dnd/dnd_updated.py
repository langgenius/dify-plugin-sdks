from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class DndUpdatedEvent(CatalogSlackEvent):
    """Slack event handler for `dnd.updated`."""

    EVENT_KEY = "dnd_updated"
