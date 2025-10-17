from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class TeamRenameEvent(CatalogSlackEvent):
    """Slack event handler for `team.rename`."""

    EVENT_KEY = "team_rename"
