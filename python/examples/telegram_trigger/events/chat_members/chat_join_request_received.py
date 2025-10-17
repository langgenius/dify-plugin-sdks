from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChatJoinRequestReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram chat_join_request updates."""

    update_key = "chat_join_request"
