from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class UserChangeEvent(CatalogSlackEvent):
    """Slack event handler for `user.change`."""

    EVENT_KEY = "user_change"
