from __future__ import annotations

from ..base import TelegramUpdateEvent


class MessageReactionUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram message_reaction updates."""

    update_key = "message_reaction"
