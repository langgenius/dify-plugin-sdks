from __future__ import annotations

from ..base import TelegramUpdateEvent


class PollStateUpdatedEvent(TelegramUpdateEvent):
    """Expose Telegram poll updates."""

    update_key = "poll"
