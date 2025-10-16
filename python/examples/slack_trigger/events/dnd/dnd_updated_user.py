from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class DndUpdatedUserEvent(CatalogSlackEvent):
    """Slack event handler for `dnd.updated.user`."""

    EVENT_KEY = "dnd_updated_user"
