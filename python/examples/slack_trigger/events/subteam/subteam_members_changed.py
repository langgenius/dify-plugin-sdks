from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class SubteamMembersChangedEvent(CatalogSlackEvent):
    """Slack event handler for `subteam.members.changed`."""

    EVENT_KEY = "subteam_members_changed"
