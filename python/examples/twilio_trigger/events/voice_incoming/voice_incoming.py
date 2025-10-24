"""
Voice Incoming Event Handler

Handles incoming voice call events from Twilio.
Triggered when a call is received on your Twilio phone number.
"""

from collections.abc import Mapping
from typing import Any

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event
from werkzeug import Request


class VoiceIncomingEventHandler(Event):
    """
    Handler for incoming voice call events.

    Triggered by Twilio's Voice URL webhook when receiving an incoming call.
    """

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        """
        Process incoming voice call webhook and apply filters.

        Args:
            request: Incoming webhook request
            parameters: User-configured filter parameters
            payload: Webhook payload (form-encoded data)

        Returns:
            Variables containing the call data

        Raises:
            EventIgnoreError: If event doesn't match filter criteria
        """
        # Extract call parameters
        from_number = payload.get("From", "")
        to_number = payload.get("To", "")
        direction = payload.get("Direction", "")

        # Only process inbound calls
        if direction and direction != "inbound":
            raise EventIgnoreError(f"Not an inbound call: {direction}")

        # Apply from_number filter
        from_filter = parameters.get("from_number", "")
        if from_filter:
            allowed_from = [num.strip() for num in from_filter.split(",")]
            if from_number not in allowed_from:
                raise EventIgnoreError(f"From number {from_number} not in filter: {allowed_from}")

        # Apply to_number filter
        to_filter = parameters.get("to_number", "")
        if to_filter:
            allowed_to = [num.strip() for num in to_filter.split(",")]
            if to_number not in allowed_to:
                raise EventIgnoreError(f"To number {to_number} not in filter: {allowed_to}")

        # Return all call data
        return Variables(variables={**payload})


__all__ = ["VoiceIncomingEventHandler"]
