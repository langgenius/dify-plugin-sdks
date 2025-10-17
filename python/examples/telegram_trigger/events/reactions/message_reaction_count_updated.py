from __future__ import annotations

from ..base import TelegramUpdateEvent


class MessageReactionCountUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram message_reaction_count updates."""

    update_key = "message_reaction_count"
