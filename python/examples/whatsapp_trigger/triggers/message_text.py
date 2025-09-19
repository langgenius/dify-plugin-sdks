from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class MessageTextTrigger(TriggerEvent):
    """
    WhatsApp Text Message Event Trigger

    This trigger handles WhatsApp text message events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle WhatsApp text message event trigger with filtering

        Parameters:
        - keyword_filter: Only trigger if message contains these keywords
        - language_filter: Only trigger for messages in these languages
        - sender_filter: Only trigger for messages from these phone numbers
        - exclude_senders: Exclude messages from these phone numbers
        - min_length: Minimum message length to trigger
        - conversation_context: Filter by conversation state (new/ongoing/all)
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
        messages = value.get("messages", [])

        if not messages:
            raise TriggerIgnoreEventError("No messages in payload")

        # Get the first text message
        message = None
        for msg in messages:
            if msg.get("type") == "text":
                message = msg
                break

        if not message:
            raise TriggerIgnoreEventError("No text message found")

        # Extract message content
        text_body = message.get("text", {}).get("body", "")
        sender_id = message.get("from", "")

        # Apply filters
        # Exclude senders filter
        exclude_senders = parameters.get("exclude_senders", "")
        if exclude_senders:
            excluded = [s.strip() for s in exclude_senders.split(",") if s.strip()]
            if sender_id in excluded:
                raise TriggerIgnoreEventError(f"Message from excluded sender: {sender_id}")

        # Sender filter (allowlist)
        sender_filter = parameters.get("sender_filter", "")
        if sender_filter:
            allowed = [s.strip() for s in sender_filter.split(",") if s.strip()]
            if allowed and sender_id not in allowed:
                raise TriggerIgnoreEventError(f"Message from non-allowed sender: {sender_id}")

        # Keyword filter
        keyword_filter = parameters.get("keyword_filter", "")
        if keyword_filter:
            keywords = [k.strip().lower() for k in keyword_filter.split(",") if k.strip()]
            if keywords:
                text_lower = text_body.lower()
                has_keyword = any(keyword in text_lower for keyword in keywords)
                if not has_keyword:
                    raise TriggerIgnoreEventError(
                        f"Message doesn't contain required keywords: {', '.join(keywords)}"
                    )

        # Minimum length filter
        min_length = parameters.get("min_length", 0)
        if min_length and len(text_body) < min_length:
            raise TriggerIgnoreEventError(
                f"Message too short: {len(text_body)} < {min_length}"
            )

        # Conversation context filter
        conversation_context = parameters.get("conversation_context", "all")
        if conversation_context != "all":
            context = message.get("context")
            is_new_conversation = context is None or not context.get("from")

            if conversation_context == "new" and not is_new_conversation:
                raise TriggerIgnoreEventError("Not a new conversation")
            elif conversation_context == "ongoing" and is_new_conversation:
                raise TriggerIgnoreEventError("Not an ongoing conversation")

        # Extract metadata
        metadata = value.get("metadata", {})
        contacts = value.get("contacts", [])
        sender_info = contacts[0] if contacts else {}

        # Detect if message is a reply
        context = message.get("context", {})
        is_reply = bool(context and context.get("from"))

        # Build variables for the workflow
        variables = {
            "message": {
                "id": message.get("id", ""),
                "type": "text",
                "text": {
                    "body": text_body
                },
                "timestamp": message.get("timestamp", ""),
                "context": {
                    "from": context.get("from", "") if context else "",
                    "id": context.get("id", "") if context else "",
                    "referred_product": {
                        "catalog_id": context.get("referred_product", {}).get("catalog_id", "") if context else "",
                        "product_retailer_id": context.get("referred_product", {}).get("product_retailer_id", "") if context else "",
                    } if context and context.get("referred_product") else None
                } if context else None
            },
            "sender": {
                "wa_id": sender_id,
                "name": sender_info.get("profile", {}).get("name", ""),
                "profile_picture_url": ""  # Not provided in standard webhook
            },
            "business": {
                "phone_number_id": metadata.get("phone_number_id", ""),
                "display_phone_number": metadata.get("display_phone_number", ""),
                "business_name": ""  # Would need additional API call to get
            },
            "conversation": {
                "id": message.get("id", ""),  # Using message ID as conversation ID
                "origin": {
                    "type": "customer_initiated"  # Default assumption
                },
                "expiry_timestamp": ""  # Would need additional context
            },
            "metadata": {
                "received_at": value.get("timestamp", ""),
                "language": "",  # Would need language detection
                "is_forwarded": message.get("forwarded", False) or message.get("frequently_forwarded", False),
                "is_reply": is_reply
            }
        }

        return Event(variables=variables)