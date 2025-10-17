from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class StarAddedEvent(CatalogSlackEvent):
    """Slack event handler for `star.added`."""

    EVENT_KEY = "star_added"
