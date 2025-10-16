from __future__ import annotations

from ..base import TelegramUpdateEvent


class InlineResultChosenEvent(TelegramUpdateEvent):
    """Expose Telegram chosen_inline_result updates."""

    update_key = "chosen_inline_result"
