from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class SubteamSelfAddedEvent(CatalogSlackEvent):
    """Slack event handler for `subteam.self.added`."""

    EVENT_KEY = "subteam_self_added"
