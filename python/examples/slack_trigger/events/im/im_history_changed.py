from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ImHistoryChangedEvent(CatalogSlackEvent):
    """Slack event handler for `im.history.changed`."""

    EVENT_KEY = "im_history_changed"
