from __future__ import annotations

from ..base import TelegramUpdateEvent


class InlineQueryReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram inline_query updates."""

    update_key = "inline_query"
