from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ImCloseEvent(CatalogSlackEvent):
    """Slack event handler for `im.close`."""

    EVENT_KEY = "im_close"
