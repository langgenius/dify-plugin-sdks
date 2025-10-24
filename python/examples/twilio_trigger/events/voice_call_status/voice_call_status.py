"""Voice Call Status Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_direction, check_from_number, check_status, check_to_number


class VoiceCallStatusEvent(Event):
    """Handle voice call status change events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process voice call status webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the call status payload

        Raises:
            EventIgnoreError: If call status doesn't match configured filters
        """
        # Filter by call status
        check_status(payload, parameters.get("status_filter"), field="CallStatus")

        # Filter by phone numbers
        check_from_number(payload, parameters.get("from_number"))
        check_to_number(payload, parameters.get("to_number"))

        # Filter by direction
        check_direction(payload, parameters.get("direction_filter"))

        # Filter by minimum duration (only for completed calls)
        min_duration = parameters.get("min_duration")
        if min_duration is not None:
            call_status = payload.get("CallStatus", "").lower()
            if call_status == "completed":
                duration = int(payload.get("Duration", 0))
                if duration < min_duration:
                    raise EventIgnoreError()

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core call identifiers
                "call_sid": payload.get("CallSid", ""),
                "account_sid": payload.get("AccountSid", ""),
                "parent_call_sid": payload.get("ParentCallSid", ""),

                # Contact information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "caller_name": payload.get("CallerName", ""),

                # Call status and direction
                "call_status": payload.get("CallStatus", ""),
                "direction": payload.get("Direction", ""),

                # Duration information
                "duration": int(payload.get("Duration", 0)),
                "call_duration": int(payload.get("CallDuration", 0)),

                # Timing information
                "timestamp": payload.get("Timestamp", ""),
                "sequence_number": payload.get("SequenceNumber", ""),
                "callback_source": payload.get("CallbackSource", ""),

                # Caller location (if available)
                "from_city": payload.get("FromCity", ""),
                "from_state": payload.get("FromState", ""),
                "from_zip": payload.get("FromZip", ""),
                "from_country": payload.get("FromCountry", ""),

                # Called party location
                "to_city": payload.get("ToCity", ""),
                "to_state": payload.get("ToState", ""),
                "to_zip": payload.get("ToZip", ""),
                "to_country": payload.get("ToCountry", ""),

                # Additional call metadata
                "forwarded_from": payload.get("ForwardedFrom", ""),
                "api_version": payload.get("ApiVersion", ""),

                # Error information (if applicable)
                "error_code": payload.get("ErrorCode", ""),
                "error_message": payload.get("ErrorMessage", ""),

                # Include full payload for advanced use cases
                **payload
            }
        )
