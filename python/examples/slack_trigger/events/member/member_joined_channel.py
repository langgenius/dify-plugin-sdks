from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MemberJoinedChannelEvent(CatalogSlackEvent):
    """Slack event handler for `member.joined.channel`."""

    EVENT_KEY = "member_joined_channel"
