from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class AppUninstalledEvent(CatalogSlackEvent):
    """Slack event handler for `app.uninstalled`."""

    EVENT_KEY = "app_uninstalled"
