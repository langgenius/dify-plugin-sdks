from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class MessageAppHomeEvent(CatalogSlackEvent):
    """Slack event handler for `message.app.home`."""

    EVENT_KEY = "message_app_home"
