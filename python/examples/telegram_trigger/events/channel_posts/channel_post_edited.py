from __future__ import annotations

from ..base import TelegramUpdateEvent


class ChannelPostEditedEvent(TelegramUpdateEvent):
    """Expose Telegram edited_channel_post updates."""

    update_key = "edited_channel_post"
