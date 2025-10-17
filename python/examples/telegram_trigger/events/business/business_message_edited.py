from __future__ import annotations

from ..base import TelegramUpdateEvent


class BusinessMessageEditedEvent(TelegramUpdateEvent):
    """Expose Telegram edited_business_message updates."""

    update_key = "edited_business_message"
