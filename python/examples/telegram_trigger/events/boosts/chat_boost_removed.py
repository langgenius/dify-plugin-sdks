from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChatBoostRemovedEvent(TelegramUpdateEvent):
    """Expose Telegram removed_chat_boost updates."""

    update_key = "removed_chat_boost"
