from __future__ import annotations

from ..base import TelegramUpdateEvent


class BusinessMessageReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram business_message updates."""

    update_key = "business_message"
