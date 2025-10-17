from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChatMemberUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram chat_member updates."""

    update_key = "chat_member"
