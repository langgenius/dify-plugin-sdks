"""Call Completed Event Handler."""

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


class CallCompletedEvent(Event):
    """Handle call completion events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process call completed webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the call completion payload

        Raises:
            EventIgnoreError: If call doesn't match configured filters
        """
        call_status = payload.get("CallStatus", "").lower()

        # Filter by call end status
        status_filter = parameters.get("call_status_filter")
        if status_filter:
            allowed_statuses = [s.lower() for s in status_filter]
            if call_status not in allowed_statuses:
                raise EventIgnoreError()

        # Filter by duration (only for completed calls)
        if call_status == "completed":
            duration = int(payload.get("Duration", 0))

            min_duration = parameters.get("min_duration")
            if min_duration is not None and duration < min_duration:
                raise EventIgnoreError()

            max_duration = parameters.get("max_duration")
            if max_duration is not None and duration > max_duration:
                raise EventIgnoreError()

        # Apply other filters
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

                # Call status and direction
                "call_status": payload.get("CallStatus", ""),
                "direction": payload.get("Direction", ""),

                # Duration information
                "duration": int(payload.get("Duration", 0)),
                "call_duration": int(payload.get("CallDuration", 0)),

                # Pricing information
                "price": payload.get("Price", ""),
                "price_unit": payload.get("PriceUnit", ""),

                # Timing information
                "timestamp": payload.get("Timestamp", ""),

                # Caller location
                "from_city": payload.get("FromCity", ""),
                "from_state": payload.get("FromState", ""),
                "from_country": payload.get("FromCountry", ""),

                # Called party location
                "to_city": payload.get("ToCity", ""),
                "to_state": payload.get("ToState", ""),
                "to_country": payload.get("ToCountry", ""),

                # Error information (if applicable)
                "error_code": payload.get("ErrorCode", ""),
                "error_message": payload.get("ErrorMessage", ""),

                # Metadata
                "api_version": payload.get("ApiVersion", ""),

                # Include full payload
                **payload
            }
        )
