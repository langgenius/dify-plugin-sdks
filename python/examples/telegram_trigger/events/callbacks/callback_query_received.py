from __future__ import annotations

from ..base import TelegramUpdateEvent


class CallbackQueryReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram callback_query updates."""

    update_key = "callback_query"
