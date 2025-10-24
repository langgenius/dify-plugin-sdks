"""Voice Ringing Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_direction, check_from_number, check_to_number


class VoiceRingingEvent(Event):
    """Handle voice call ringing events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """Process voice ringing webhook and apply filters."""
        call_status = payload.get("CallStatus", "").lower()
        if call_status != "ringing":
            raise EventIgnoreError()

        check_from_number(payload, parameters.get("from_number"))
        check_to_number(payload, parameters.get("to_number"))
        check_direction(payload, parameters.get("direction_filter"))

        return Variables(
            variables={
                "call_sid": payload.get("CallSid", ""),
                "account_sid": payload.get("AccountSid", ""),
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "call_status": payload.get("CallStatus", ""),
                "direction": payload.get("Direction", ""),
                "timestamp": payload.get("Timestamp", ""),
                "callback_source": payload.get("CallbackSource", ""),
                "sequence_number": payload.get("SequenceNumber", ""),
                **payload,
            }
        )


__all__ = ["VoiceRingingEvent"]
