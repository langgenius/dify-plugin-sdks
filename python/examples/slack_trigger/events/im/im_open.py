from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ImOpenEvent(CatalogSlackEvent):
    """Slack event handler for `im.open`."""

    EVENT_KEY = "im_open"
