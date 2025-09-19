from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class MessageImageTrigger(TriggerEvent):
    """
    WhatsApp Image Message Event Trigger

    This trigger handles WhatsApp image message events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle WhatsApp image message event trigger with filtering

        Parameters:
        - has_caption: Filter based on caption presence (yes/no/any)
        - caption_keywords: Only trigger if caption contains these keywords
        - sender_filter: Only trigger for images from these phone numbers
        - max_file_size: Maximum file size in MB to trigger
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

        # Get the first image message
        message = None
        for msg in messages:
            if msg.get("type") == "image":
                message = msg
                break

        if not message:
            raise TriggerIgnoreEventError("No image message found")

        # Extract image information
        image_data = message.get("image", {})
        caption = image_data.get("caption", "")
        sender_id = message.get("from", "")

        # Apply filters
        # Sender filter
        sender_filter = parameters.get("sender_filter", "")
        if sender_filter:
            allowed = [s.strip() for s in sender_filter.split(",") if s.strip()]
            if allowed and sender_id not in allowed:
                raise TriggerIgnoreEventError(f"Image from non-allowed sender: {sender_id}")

        # Caption presence filter
        has_caption = parameters.get("has_caption", "any")
        if has_caption == "yes" and not caption:
            raise TriggerIgnoreEventError("Image doesn't have a caption")
        elif has_caption == "no" and caption:
            raise TriggerIgnoreEventError("Image has a caption but shouldn't")

        # Caption keyword filter
        caption_keywords = parameters.get("caption_keywords", "")
        if caption_keywords and caption:
            keywords = [k.strip().lower() for k in caption_keywords.split(",") if k.strip()]
            if keywords:
                caption_lower = caption.lower()
                has_keyword = any(keyword in caption_lower for keyword in keywords)
                if not has_keyword:
                    raise TriggerIgnoreEventError(
                        f"Caption doesn't contain required keywords: {', '.join(keywords)}"
                    )

        # File size filter (would need additional API call to get actual size)
        # This is a placeholder - actual implementation would need to fetch media details
        max_file_size = parameters.get("max_file_size")
        # Note: File size checking would require downloading the media or making an API call

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
                "type": "image",
                "image": {
                    "id": image_data.get("id", ""),
                    "mime_type": image_data.get("mime_type", ""),
                    "sha256": image_data.get("sha256", ""),
                    "caption": caption,
                    "url": ""  # URL needs to be fetched separately via API
                },
                "timestamp": message.get("timestamp", ""),
                "context": {
                    "from": context.get("from", "") if context else "",
                    "id": context.get("id", "") if context else "",
                } if context else None
            },
            "sender": {
                "wa_id": sender_id,
                "name": sender_info.get("profile", {}).get("name", ""),
            },
            "business": {
                "phone_number_id": metadata.get("phone_number_id", ""),
                "display_phone_number": metadata.get("display_phone_number", ""),
            },
            "metadata": {
                "received_at": value.get("timestamp", ""),
                "file_size": 0,  # Would need API call to get actual size
                "is_forwarded": message.get("forwarded", False) or message.get("frequently_forwarded", False),
                "is_reply": is_reply
            }
        }

        return Event(variables=variables)