"""Voice Completed Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_direction, check_from_number, check_to_number


TERMINAL_STATUSES = {"completed", "busy", "no-answer", "canceled", "failed"}


class VoiceCompletedEvent(Event):
    """Handle voice call completion events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """Process voice completion webhook and apply filters."""
        call_status = payload.get("CallStatus", "").lower()
        if call_status not in TERMINAL_STATUSES:
            raise EventIgnoreError()

        check_from_number(payload, parameters.get("from_number"))
        check_to_number(payload, parameters.get("to_number"))
        check_direction(payload, parameters.get("direction_filter"))

        # Duration-based filters apply only when Twilio sends duration fields (usually completed)
        min_duration = parameters.get("min_duration")
        max_duration = parameters.get("max_duration")
        if call_status == "completed":
            duration = int(payload.get("Duration", 0))
            if min_duration is not None and duration < min_duration:
                raise EventIgnoreError()
            if max_duration is not None and duration > max_duration:
                raise EventIgnoreError()

        return Variables(
            variables={
                "call_sid": payload.get("CallSid", ""),
                "account_sid": payload.get("AccountSid", ""),
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "call_status": payload.get("CallStatus", ""),
                "direction": payload.get("Direction", ""),
                "duration": int(payload.get("Duration", 0)),
                "call_duration": int(payload.get("CallDuration", 0)),
                "timestamp": payload.get("Timestamp", ""),
                "callback_source": payload.get("CallbackSource", ""),
                "sequence_number": payload.get("SequenceNumber", ""),
                "price": payload.get("Price", ""),
                "price_unit": payload.get("PriceUnit", ""),
                "error_code": payload.get("ErrorCode", ""),
                "error_message": payload.get("ErrorMessage", ""),
                **payload,
            }
        )


__all__ = ["VoiceCompletedEvent"]
