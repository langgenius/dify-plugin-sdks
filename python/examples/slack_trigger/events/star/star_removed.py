from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class StarRemovedEvent(CatalogSlackEvent):
    """Slack event handler for `star.removed`."""

    EVENT_KEY = "star_removed"
