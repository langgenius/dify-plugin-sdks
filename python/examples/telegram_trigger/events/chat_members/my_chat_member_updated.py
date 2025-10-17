from __future__ import annotations

from ..base import TelegramUpdateEvent


class MyChatMemberUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram my_chat_member updates."""

    update_key = "my_chat_member"
