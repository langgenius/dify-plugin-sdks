from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class SubteamSelfRemovedEvent(CatalogSlackEvent):
    """Slack event handler for `subteam.self.removed`."""

    EVENT_KEY = "subteam_self_removed"
