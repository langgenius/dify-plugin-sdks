from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class SubteamUpdatedEvent(CatalogSlackEvent):
    """Slack event handler for `subteam.updated`."""

    EVENT_KEY = "subteam_updated"
