from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class PinRemovedEvent(CatalogSlackEvent):
    """Slack event handler for `pin.removed`."""

    EVENT_KEY = "pin_removed"
