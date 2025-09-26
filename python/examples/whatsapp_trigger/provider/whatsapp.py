import time
import uuid
from collections.abc import Mapping
from typing import Any

import requests
from utils.dynamic_options import fetch_phone_numbers
from utils.signature_validator import validate_signature
from werkzeug import Request, Response

from dify_plugin.entities import ParameterOption
from dify_plugin.entities.trigger import Subscription, TriggerDispatch, UnsubscribeResult
from dify_plugin.errors.trigger import (
    TriggerDispatchError,
    TriggerProviderCredentialValidationError,
    TriggerValidationError,
)
from dify_plugin.interfaces.trigger import TriggerProvider


class WhatsAppProvider(TriggerProvider):
    """
    WhatsApp Business Platform Trigger Provider

    Handles webhook subscriptions and event dispatching for WhatsApp messages
    and status updates.
    """

    _GRAPH_API_URL = "https://graph.facebook.com/v19.0"
    _WEBHOOK_FIELDS = "messages,message_status,messaging_product"

    def _validate_credentials(self, credentials: dict) -> None:
        """
        Validate WhatsApp Business API credentials
        """
        try:
            if "system_access_token" not in credentials or not credentials.get("system_access_token"):
                raise TriggerProviderCredentialValidationError("System Access Token is required.")
            if "app_secret" not in credentials or not credentials.get("app_secret"):
                raise TriggerProviderCredentialValidationError("App Secret is required.")

            # Test the token by fetching user info
            headers = {
                "Authorization": f"Bearer {credentials['system_access_token']}",
                "Content-Type": "application/json",
            }
            response = requests.get(f"{self._GRAPH_API_URL}/me", headers=headers, timeout=10)

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", "Invalid credentials")
                raise TriggerProviderCredentialValidationError(f"Failed to validate credentials: {error_msg}")

        except Exception as e:
            raise TriggerProviderCredentialValidationError(str(e)) from e

    def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Dispatch WhatsApp webhook events to appropriate triggers
        """
        # Handle webhook verification (GET request)
        if request.method == "GET":
            return self._handle_verification(subscription, request)

        # Verify webhook signature for POST requests
        app_secret = self.runtime.credentials.get("app_secret")
        if app_secret and not validate_signature(request, app_secret):
            raise TriggerValidationError("Invalid webhook signature")

        try:
            payload = request.get_json(force=True)
            if not payload:
                raise TriggerDispatchError("Empty request body")
        except Exception as e:
            raise TriggerDispatchError(f"Failed to parse payload: {e}") from e

        # Extract WhatsApp event data
        entry = payload.get("entry", [])
        if not entry:
            return TriggerDispatch(
                triggers=[], response=Response('{"status": "ok"}', status=200, mimetype="application/json")
            )

        triggers = []

        for entry_item in entry:
            changes = entry_item.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Handle message events
                messages = value.get("messages", [])
                for message in messages:
                    message_triggers = self._process_message(message, subscription)
                    triggers.extend(message_triggers)

                # Handle status events
                statuses = value.get("statuses", [])
                for status in statuses:
                    status_triggers = self._process_status(status, subscription)
                    triggers.extend(status_triggers)

        response = Response('{"status": "ok"}', status=200, mimetype="application/json")
        return TriggerDispatch(triggers=triggers, response=response)

    def _handle_verification(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Handle WhatsApp webhook verification challenge
        """
        verify_token = subscription.properties.get("webhook_verify_token")
        hub_mode = request.args.get("hub.mode")
        hub_token = request.args.get("hub.verify_token")
        hub_challenge = request.args.get("hub.challenge")

        if hub_mode == "subscribe" and hub_token == verify_token:
            # Return the challenge to verify the webhook
            response = Response(hub_challenge, status=200, mimetype="text/plain")
            return TriggerDispatch(triggers=[], response=response)
        else:
            raise TriggerValidationError("Failed webhook verification")

    def _process_message(self, message: dict, subscription: Subscription) -> list[str]:
        """
        Process a WhatsApp message and determine which triggers to fire
        """
        triggers = []
        message_type = message.get("type")

        # Check if we should filter by message type
        message_types_filter = subscription.parameters.get("message_types", [])
        if message_types_filter and message_type not in message_types_filter:
            return triggers

        # Map message types to trigger names
        if message_type == "text":
            triggers.append("message_text")
        elif message_type == "image":
            triggers.append("message_image")
        elif message_type == "video":
            triggers.append("message_video")
        elif message_type == "audio":
            triggers.append("message_audio")
        elif message_type == "document":
            triggers.append("message_document")
        elif message_type == "location":
            triggers.append("message_location")
        elif message_type == "contacts":
            triggers.append("message_contacts")
        elif message_type == "sticker":
            triggers.append("message_sticker")
        elif message_type == "reaction":
            triggers.append("message_reaction")
        elif message_type == "interactive":
            # Handle interactive message types
            interactive_type = message.get("interactive", {}).get("type")
            if interactive_type == "button_reply":
                triggers.append("interactive_button_reply")
            elif interactive_type == "list_reply":
                triggers.append("interactive_list_reply")
        elif message_type == "order":
            triggers.append("order_received")

        return triggers

    def _process_status(self, status: dict, subscription: Subscription) -> list[str]:
        """
        Process a WhatsApp status update and determine which triggers to fire
        """
        triggers = []
        status_type = status.get("status")

        # Map status types to trigger names
        if status_type == "sent":
            triggers.append("message_sent")
        elif status_type == "delivered":
            triggers.append("message_delivered")
        elif status_type == "read":
            triggers.append("message_read")
        elif status_type == "failed":
            triggers.append("message_failed")

        return triggers

    def _subscribe(self, endpoint: str, credentials: Mapping[str, Any], parameters: Mapping[str, Any]) -> Subscription:
        """
        Create a WhatsApp webhook subscription

        Note: WhatsApp webhooks are configured at the app level in Meta Business,
        so this mainly returns subscription info for internal tracking.
        """
        webhook_id = uuid.uuid4().hex
        webhook_verify_token = webhook_id  # Use UUID as default verify token
        phone_number_id = parameters.get("phone_number_id")
        events = parameters.get("events", ["messages"])

        if not phone_number_id:
            raise ValueError("phone_number_id is required")

        # WhatsApp webhooks are configured at the app level, not per phone number
        # We return subscription info for Dify to track
        return Subscription(
            expires_at=int(time.time()) + 365 * 24 * 60 * 60,  # 1 year expiration
            endpoint=endpoint,
            properties={
                "external_id": webhook_id,
                "phone_number_id": phone_number_id,
                "events": events,
                "webhook_verify_token": webhook_verify_token,
                "active": True,
            },
        )

    def _unsubscribe(
        self, endpoint: str, subscription: Subscription, credentials: Mapping[str, Any]
    ) -> UnsubscribeResult:
        """
        Remove a WhatsApp webhook subscription

        Note: WhatsApp webhooks are managed at the app level in Meta Business,
        so this mainly marks the subscription as inactive internally.
        """
        return UnsubscribeResult(success=True, message="WhatsApp webhook subscription removed successfully")

    def _refresh(self, endpoint: str, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        """
        Refresh a WhatsApp webhook subscription (extend expiration)
        """
        # Simply return the subscription with extended expiration
        return Subscription(
            expires_at=int(time.time()) + 365 * 24 * 60 * 60,  # Extend by 1 year
            endpoint=endpoint,
            properties=subscription.properties,
        )

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch dynamic parameter options
        """
        if parameter == "phone_number_id":
            return fetch_phone_numbers(self.runtime.credentials.get("system_access_token"))

        return []
