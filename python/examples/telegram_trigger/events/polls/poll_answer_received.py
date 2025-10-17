from __future__ import annotations

from ..base import TelegramUpdateEvent


class PollAnswerReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram poll_answer updates."""

    update_key = "poll_answer"
