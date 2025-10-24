"""SMS Incoming Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import (
    check_body_contains,
    check_from_number,
    check_has_media,
    check_to_number,
)


class SmsIncomingEvent(Event):
    """Handle incoming SMS message events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process incoming SMS webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the SMS payload

        Raises:
            EventIgnoreError: If message doesn't match configured filters
        """
        # Apply filters
        check_from_number(payload, parameters.get("from_number"))
        check_to_number(payload, parameters.get("to_number"))
        check_body_contains(payload, parameters.get("body_contains"))
        check_has_media(payload, parameters.get("has_media"))

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core message identifiers
                "message_sid": payload.get("MessageSid", ""),
                "account_sid": payload.get("AccountSid", ""),
                "messaging_service_sid": payload.get("MessagingServiceSid", ""),

                # Contact information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),

                # Message content
                "body": payload.get("Body", ""),
                "num_media": int(payload.get("NumMedia", 0)),
                "num_segments": int(payload.get("NumSegments", 1)),

                # Status
                "sms_status": payload.get("SmsStatus", ""),

                # Sender location (if available)
                "from_city": payload.get("FromCity", ""),
                "from_state": payload.get("FromState", ""),
                "from_zip": payload.get("FromZip", ""),
                "from_country": payload.get("FromCountry", ""),

                # Recipient location
                "to_city": payload.get("ToCity", ""),
                "to_state": payload.get("ToState", ""),
                "to_zip": payload.get("ToZip", ""),
                "to_country": payload.get("ToCountry", ""),

                # Additional metadata
                "api_version": payload.get("ApiVersion", ""),
                "add_ons": payload.get("AddOns", ""),

                # Include full payload for advanced use cases
                **payload
            }
        )
