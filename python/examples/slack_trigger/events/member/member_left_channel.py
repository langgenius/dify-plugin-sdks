from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MemberLeftChannelEvent(CatalogSlackEvent):
    """Slack event handler for `member.left.channel`."""

    EVENT_KEY = "member_left_channel"
