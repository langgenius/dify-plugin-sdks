from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ImCreatedEvent(CatalogSlackEvent):
    """Slack event handler for `im.created`."""

    EVENT_KEY = "im_created"
