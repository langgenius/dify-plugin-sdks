from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class PinAddedEvent(CatalogSlackEvent):
    """Slack event handler for `pin.added`."""

    EVENT_KEY = "pin_added"
