from __future__ import annotations

from ..base import TelegramUpdateEvent


class ShippingQueryReceivedEvent(TelegramUpdateEvent):
    """Expose Telegram shipping_query updates."""

    update_key = "shipping_query"
