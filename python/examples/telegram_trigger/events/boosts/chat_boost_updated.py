from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChatBoostUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram chat_boost updates."""

    update_key = "chat_boost"
