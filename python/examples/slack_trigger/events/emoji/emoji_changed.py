from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class EmojiChangedEvent(CatalogSlackEvent):
    """Slack event handler for `emoji.changed`."""

    EVENT_KEY = "emoji_changed"
