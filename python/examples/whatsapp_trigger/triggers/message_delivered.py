from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class MessageDeliveredTrigger(TriggerEvent):
    """
    WhatsApp Message Delivered Status Event Trigger

    This trigger handles WhatsApp message delivered status events and extracts
    relevant information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle WhatsApp message delivered status event trigger with filtering

        Parameters:
        - recipient_filter: Only trigger for deliveries to these phone numbers
        - message_type_filter: Filter by message type
        - include_conversation_id: Include conversation thread ID in output
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract the first entry and change
        entry = payload.get("entry", [])
        if not entry:
            raise TriggerIgnoreEventError("No entry in payload")

        changes = entry[0].get("changes", [])
        if not changes:
            raise TriggerIgnoreEventError("No changes in entry")

        value = changes[0].get("value", {})
        statuses = value.get("statuses", [])

        if not statuses:
            raise TriggerIgnoreEventError("No statuses in payload")

        # Get the first delivered status
        status = None
        for st in statuses:
            if st.get("status") == "delivered":
                status = st
                break

        if not status:
            raise TriggerIgnoreEventError("No delivered status found")

        # Extract status information
        recipient_id = status.get("recipient_id", "")

        # Apply filters
        # Recipient filter
        recipient_filter = parameters.get("recipient_filter", "")
        if recipient_filter:
            allowed = [r.strip() for r in recipient_filter.split(",") if r.strip()]
            if allowed and recipient_id not in allowed:
                raise TriggerIgnoreEventError(f"Delivery to non-filtered recipient: {recipient_id}")

        # Extract metadata
        metadata = value.get("metadata", {})

        # Get conversation information
        conversation = status.get("conversation", {})
        include_conversation = parameters.get("include_conversation_id", "yes") == "yes"

        # Get pricing information
        pricing = status.get("pricing", {})

        # Build variables for the workflow
        variables = {
            "status": {
                "id": status.get("id", ""),
                "status": "delivered",
                "timestamp": status.get("timestamp", ""),
                "recipient_id": recipient_id,
            },
            "business": {
                "phone_number_id": metadata.get("phone_number_id", ""),
                "display_phone_number": metadata.get("display_phone_number", ""),
            },
            "metadata": {
                "delivered_at": status.get("timestamp", ""),
                "delivery_attempts": 1,  # WhatsApp doesn't provide this, defaulting to 1
                "message_type": "unknown",  # Would need to track from original send
            }
        }

        # Add conversation info if requested
        if include_conversation and conversation:
            variables["status"]["conversation"] = {
                "id": conversation.get("id", ""),
                "origin": {
                    "type": conversation.get("origin", {}).get("type", "")
                },
                "expiry_timestamp": conversation.get("expiry_timestamp", "")
            }

        # Add pricing info if available
        if pricing:
            variables["status"]["pricing"] = {
                "billable": pricing.get("billable", False),
                "pricing_model": pricing.get("pricing_model", ""),
                "category": pricing.get("category", "")
            }

        return Event(variables=variables)