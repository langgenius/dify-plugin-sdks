from __future__ import annotations

from ..base import TelegramUpdateEvent


class PreCheckoutQueryReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram pre_checkout_query updates."""

    update_key = "pre_checkout_query"
