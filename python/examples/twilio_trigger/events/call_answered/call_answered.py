"""Call Answered Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_direction, check_from_number, check_to_number


class CallAnsweredEvent(Event):
    """Handle call answered events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process call answered webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the call answered payload

        Raises:
            EventIgnoreError: If call doesn't match configured filters
        """
        # Ensure this is an answered call (CallStatus should be 'in-progress')
        call_status = payload.get("CallStatus", "").lower()
        if call_status != "in-progress":
            raise EventIgnoreError()

        # Apply filters
        check_from_number(payload, parameters.get("from_number"))
        check_to_number(payload, parameters.get("to_number"))
        check_direction(payload, parameters.get("direction_filter"))

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core call identifiers
                "call_sid": payload.get("CallSid", ""),
                "account_sid": payload.get("AccountSid", ""),

                # Contact information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "caller_name": payload.get("CallerName", ""),

                # Call status and direction
                "call_status": payload.get("CallStatus", ""),
                "direction": payload.get("Direction", ""),

                # Timing information
                "timestamp": payload.get("Timestamp", ""),
                "sequence_number": payload.get("SequenceNumber", ""),
                "callback_source": payload.get("CallbackSource", ""),

                # Caller location
                "from_city": payload.get("FromCity", ""),
                "from_state": payload.get("FromState", ""),
                "from_country": payload.get("FromCountry", ""),

                # Called party location
                "to_city": payload.get("ToCity", ""),
                "to_state": payload.get("ToState", ""),
                "to_country": payload.get("ToCountry", ""),

                # Metadata
                "api_version": payload.get("ApiVersion", ""),

                # Include full payload
                **payload
            }
        )
