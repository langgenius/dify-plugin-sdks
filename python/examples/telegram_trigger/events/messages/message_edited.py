from __future__ import annotations

from ..base import TelegramUpdateEvent


class MessageEditedEvent(TelegramUpdateEvent):
    """Expose Telegram edited_message updates."""

    update_key = "edited_message"
