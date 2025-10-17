from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class TokensRevokedEvent(CatalogSlackEvent):
    """Slack event handler for `tokens.revoked`."""

    EVENT_KEY = "tokens_revoked"
