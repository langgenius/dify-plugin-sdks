from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class LinkSharedEvent(CatalogSlackEvent):
    """Slack event handler for `link.shared`."""

    EVENT_KEY = "link_shared"
