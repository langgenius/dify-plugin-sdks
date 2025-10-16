from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ResourcesRemovedEvent(CatalogSlackEvent):
    """Slack event handler for `resources.removed`."""

    EVENT_KEY = "resources_removed"
