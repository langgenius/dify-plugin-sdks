"""WhatsApp Incoming Message Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_body_contains, check_from_number, check_has_media


class WhatsappIncomingEvent(Event):
    """Handle incoming WhatsApp message events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process incoming WhatsApp webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the WhatsApp message payload

        Raises:
            EventIgnoreError: If message doesn't match configured filters
        """
        # Apply filters
        check_from_number(payload, parameters.get("from_number"))
        check_body_contains(payload, parameters.get("body_contains"))
        check_has_media(payload, parameters.get("has_media"))

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core message identifiers
                "message_sid": payload.get("MessageSid", ""),
                "account_sid": payload.get("AccountSid", ""),

                # WhatsApp-specific identifiers
                "wa_id": payload.get("WaId", ""),
                "profile_name": payload.get("ProfileName", ""),

                # Contact information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),

                # Message content
                "body": payload.get("Body", ""),
                "num_media": int(payload.get("NumMedia", 0)),
                "num_segments": int(payload.get("NumSegments", 1)),

                # Status
                "sms_status": payload.get("SmsStatus", ""),

                # Additional metadata
                "api_version": payload.get("ApiVersion", ""),

                # Include full payload for advanced use cases
                **payload
            }
        )
