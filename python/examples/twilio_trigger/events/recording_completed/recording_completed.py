"""Recording Completed Event Handler."""

from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event

# Import shared filter utilities
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.common import check_from_number


class RecordingCompletedEvent(Event):
    """Handle recording completion events."""

    def _on_event(self, request: Request, parameters: dict[str, Any], payload: dict[str, Any]) -> Variables:
        """
        Process recording completed webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the recording completion payload

        Raises:
            EventIgnoreError: If recording doesn't match configured filters
        """
        # Filter by recording status
        status_filter = parameters.get("recording_status_filter")
        if status_filter:
            recording_status = payload.get("RecordingStatus", "").lower()
            allowed_statuses = [s.lower() for s in status_filter]
            if recording_status not in allowed_statuses:
                raise EventIgnoreError()

        # Filter by minimum duration (only for completed recordings)
        min_duration = parameters.get("min_duration")
        if min_duration is not None:
            recording_status = payload.get("RecordingStatus", "").lower()
            if recording_status == "completed":
                duration = int(payload.get("RecordingDuration", 0))
                if duration < min_duration:
                    raise EventIgnoreError()

        # Filter by caller number
        check_from_number(payload, parameters.get("from_number"))

        # Extract and return all relevant data
        return Variables(
            variables={
                # Core recording identifiers
                "recording_sid": payload.get("RecordingSid", ""),
                "account_sid": payload.get("AccountSid", ""),
                "call_sid": payload.get("CallSid", ""),

                # Recording status and metadata
                "recording_status": payload.get("RecordingStatus", ""),
                "recording_url": payload.get("RecordingUrl", ""),
                "recording_duration": int(payload.get("RecordingDuration", 0)),
                "recording_channels": int(payload.get("RecordingChannels", 1)),
                "recording_source": payload.get("RecordingSource", ""),
                "recording_start_time": payload.get("RecordingStartTime", ""),

                # Call information
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "call_duration": int(payload.get("CallDuration", 0)),

                # Error information (if applicable)
                "error_code": payload.get("ErrorCode", ""),

                # Metadata
                "api_version": payload.get("ApiVersion", ""),

                # Include full payload for advanced use cases
                **payload
            }
        )
