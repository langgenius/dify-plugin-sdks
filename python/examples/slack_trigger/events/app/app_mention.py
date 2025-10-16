from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class AppMentionEvent(CatalogSlackEvent):
    """Slack event handler for `app.mention`."""

    EVENT_KEY = "app_mention"
