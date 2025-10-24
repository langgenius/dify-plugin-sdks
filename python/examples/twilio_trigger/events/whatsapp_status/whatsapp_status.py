"""WhatsApp Status Callback Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_status, check_to_number


class WhatsappStatusEvent(Event):
    """Handle WhatsApp status callback events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process WhatsApp status webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the WhatsApp status payload

        Raises:
            EventIgnoreError: If status update doesn't match configured filters
        """
        # Filter by status
        check_status(payload, parameters.get("status_filter"), field="MessageStatus")

        # Filter by recipient number
        check_to_number(payload, parameters.get("to_number"))

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core message identifiers
                "message_sid": payload.get("MessageSid", ""),
                "account_sid": payload.get("AccountSid", ""),

                # Contact information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),

                # Status information
                "message_status": payload.get("MessageStatus", ""),
                "error_code": payload.get("ErrorCode", ""),
                "error_message": payload.get("ErrorMessage", ""),

                # Message content
                "body": payload.get("Body", ""),

                # WhatsApp-specific fields
                "channel_to_address": payload.get("ChannelToAddress", ""),

                # Metadata
                "api_version": payload.get("ApiVersion", ""),

                # Include full payload for advanced use cases
                **payload
            }
        )
