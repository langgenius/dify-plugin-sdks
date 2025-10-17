from __future__ import annotations

from ..base import TelegramUpdateEvent


class BusinessConnectionUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram business_connection updates."""

    update_key = "business_connection"
