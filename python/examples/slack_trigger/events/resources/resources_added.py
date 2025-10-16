from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ResourcesAddedEvent(CatalogSlackEvent):
    """Slack event handler for `resources.added`."""

    EVENT_KEY = "resources_added"
