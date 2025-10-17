from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class AppRateLimitedEvent(CatalogSlackEvent):
    """Slack event handler for `app.rate.limited`."""

    EVENT_KEY = "app_rate_limited"
