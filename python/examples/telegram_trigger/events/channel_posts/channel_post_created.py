from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChannelPostCreatedEvent(TelegramUpdateEvent):
    """Expose Telegram channel_post updates."""

    update_key = "channel_post"
