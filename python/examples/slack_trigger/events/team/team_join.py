from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class TeamJoinEvent(CatalogSlackEvent):
    """Slack event handler for `team.join`."""

    EVENT_KEY = "team_join"
