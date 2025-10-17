from __future__ import annotations

from ..base import TelegramUpdateEvent


class BusinessMessagesDeletedEvent(TelegramUpdateEvent):
    """Expose Telegram deleted_business_messages updates."""

    update_key = "deleted_business_messages"
