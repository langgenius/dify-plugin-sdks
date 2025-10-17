from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class SubteamCreatedEvent(CatalogSlackEvent):
    """Slack event handler for `subteam.created`."""

    EVENT_KEY = "subteam_created"
