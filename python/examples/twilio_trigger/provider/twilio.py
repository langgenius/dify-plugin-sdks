from __future__ import annotations

import secrets
import time
import urllib.parse
from typing import Any
from urllib.parse import urlencode

import requests
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from werkzeug import Request, Response

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import TriggerOAuthCredentials
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import EventDispatch, Subscription, UnsubscribeResult
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerDispatchError,
    TriggerProviderCredentialValidationError,
    TriggerProviderOAuthError,
    TriggerValidationError,
    UnsubscribeError,
)
from dify_plugin.interfaces.trigger import Trigger, TriggerSubscriptionConstructor


VOICE_INCOMING_EVENT_TYPE = "incoming_voice_call"
VOICE_STATUS_EVENT_TYPE = "call_status_callback"
RECORDING_STATUS_EVENT_TYPE = "recording_status_callback"


class TwilioTrigger(Trigger):
    """Handle Twilio webhook event dispatch."""

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        """
        Dispatch incoming Twilio webhook events.

        Validates signature, extracts event type from query parameters,
        and routes to appropriate event handlers.
        """
        # 1. Validate webhook signature
        auth_token = subscription.properties.get("auth_token")
        if auth_token:
            self._validate_signature(request=request, auth_token=auth_token)

        # 2. Get event type from query parameter
        event_type: str | None = request.args.get("event_type")
        if not event_type:
            raise TriggerDispatchError(
                message="Missing event_type query parameter",
                error_code="MISSING_EVENT_TYPE"
            )

        # 3. Extract user identifier (MessageSid or CallSid)
        payload = self._extract_payload(request)
        user_id = payload.get("MessageSid") or payload.get("CallSid") or ""

        # 4. Route to event handlers
        events: list[str] = self._dispatch_trigger_events(event_type=event_type, payload=payload)

        # 5. Return TwiML response (empty Response for status callbacks)
        response = Response(
            response='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            status=200,
            mimetype="application/xml"
        )

        return EventDispatch(
            user_id=user_id,
            events=events,
            response=response,
            payload=payload,
        )

    def _dispatch_trigger_events(self, event_type: str, payload: dict[str, Any]) -> list[str]:
        """
        Map Twilio event types to internal event identifiers.

        Args:
            event_type: Event type from query parameter (e.g., "sms_incoming", "call_status_callback")
            payload: Webhook payload data

        Returns:
            List of event identifiers to trigger
        """
        event_type = event_type.lower()

        # SMS Events
        if event_type == "sms_incoming":
            return ["sms_incoming"]

        if event_type == "sms_status":
            return ["sms_status"]

        # Voice Call Events
        if event_type == VOICE_INCOMING_EVENT_TYPE:
            return ["voice_incoming"]

        if event_type == VOICE_STATUS_EVENT_TYPE:
            # Route to multiple event handlers based on CallStatus
            call_status = payload.get("CallStatus", "").lower()
            events = ["voice_call_status"]  # Always trigger general event

            # Also trigger specific events
            if call_status in {"queued", "initiated"}:
                events.append("voice_initiated")
            if call_status == "ringing":
                events.append("voice_ringing")
            if call_status == "in-progress":
                events.append("voice_answered")
                events.append("call_answered")
            if call_status in {"completed", "busy", "no-answer", "canceled", "failed"}:
                events.append("voice_completed")
                events.append("call_completed")

            return events

        # WhatsApp Events
        if event_type == "whatsapp_incoming":
            return ["whatsapp_incoming"]

        if event_type == "whatsapp_status":
            return ["whatsapp_status"]

        # Recording Events
        if event_type == RECORDING_STATUS_EVENT_TYPE:
            return ["recording_completed"]

        raise TriggerDispatchError(
            message=f"Unknown Twilio event type: {event_type}",
            error_code="UNKNOWN_EVENT_TYPE"
        )

    def _validate_signature(self, request: Request, auth_token: str) -> None:
        """
        Validate Twilio webhook signature using HMAC-SHA1.

        Twilio signs requests with X-Twilio-Signature header using:
        - Full URL (including query parameters)
        - POST parameters (sorted by key)
        - HMAC-SHA1 with auth_token as key
        - Base64 encoded result

        Args:
            request: Incoming webhook request
            auth_token: Twilio Auth Token for signature validation

        Raises:
            TriggerValidationError: If signature is missing or invalid
        """
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            raise TriggerValidationError(
                message="Missing X-Twilio-Signature header",
                error_code="MISSING_SIGNATURE"
            )

        # Use Twilio's official validator
        validator = RequestValidator(auth_token)

        # Get full URL (Twilio validates against the complete URL)
        url = request.url

        # Get POST parameters as dict
        params = request.form.to_dict() if request.method == "POST" else {}

        # Validate signature
        if not validator.validate(url, params, signature):
            raise TriggerValidationError(
                message="Invalid Twilio signature - request may not be from Twilio",
                error_code="INVALID_SIGNATURE",
                external_response={
                    "url": url,
                    "signature_received": signature
                }
            )

    def _extract_payload(self, request: Request) -> dict[str, Any]:
        """
        Extract payload from Twilio webhook request.

        Twilio sends data as application/x-www-form-urlencoded.

        Args:
            request: Incoming webhook request

        Returns:
            Dictionary of webhook parameters

        Raises:
            TriggerDispatchError: If payload is empty or invalid
        """
        if request.method != "POST":
            raise TriggerDispatchError(
                message="Twilio webhooks must use POST method",
                error_code="INVALID_METHOD"
            )

        payload = request.form.to_dict()

        if not payload:
            raise TriggerDispatchError(
                message="Empty webhook payload",
                error_code="EMPTY_PAYLOAD"
            )

        return payload


class TwilioSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Manage Twilio webhook subscriptions."""

    def _validate_api_key(self, credentials: dict[str, Any]) -> None:
        """
        Validate Twilio credentials by making an API call.

        Supports two authentication methods:
        1. Auth Token: account_sid + auth_token (for development)
        2. API Key: account_sid + api_key_sid + api_key_secret (for production)

        Args:
            credentials: Dict with authentication credentials

        Raises:
            TriggerProviderCredentialValidationError: If credentials are invalid or missing
        """
        account_sid = credentials.get("account_sid")

        # Check for API Key authentication (recommended for production)
        api_key_sid = credentials.get("api_key_sid")
        api_key_secret = credentials.get("api_key_secret")

        # Check for Auth Token authentication (for development)
        auth_token = credentials.get("auth_token")

        if api_key_sid and api_key_secret:
            # API Key authentication
            if not account_sid:
                raise TriggerProviderCredentialValidationError(
                    "Missing account_sid for API Key authentication"
                )

            try:
                # For API Keys, pass (api_key_sid, api_key_secret, account_sid)
                client = Client(api_key_sid, api_key_secret, account_sid)
                client.api.accounts(account_sid).fetch()
            except Exception as e:
                raise TriggerProviderCredentialValidationError(
                    f"Invalid Twilio API Key credentials: {str(e)}"
                )

        elif auth_token:
            # Auth Token authentication
            if not account_sid:
                raise TriggerProviderCredentialValidationError(
                    "Missing account_sid for Auth Token authentication"
                )

            try:
                # For Auth Token, pass (account_sid, auth_token)
                client = Client(account_sid, auth_token)
                client.api.accounts(account_sid).fetch()
            except Exception as e:
                raise TriggerProviderCredentialValidationError(
                    f"Invalid Twilio Auth Token credentials: {str(e)}"
                )

        else:
            raise TriggerProviderCredentialValidationError(
                "Must provide either (api_key_sid + api_key_secret) or (account_sid + auth_token)"
            )

    def _create_subscription(
        self,
        endpoint: str,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        """
        Create Twilio webhook subscription by configuring phone number webhooks.

        Args:
            endpoint: Dify webhook endpoint URL
            parameters: Subscription parameters (phone_number_sid, events)
            credentials: Twilio credentials (auth_token or api_key)
            credential_type: Credential type

        Returns:
            Subscription object with webhook configuration

        Raises:
            SubscriptionError: If webhook creation fails
        """
        account_sid = credentials.get("account_sid")
        phone_number_sid = parameters.get("phone_number_sid")
        events = parameters.get("events", [])

        if not phone_number_sid:
            raise SubscriptionError(
                message="Missing phone_number_sid parameter",
                error_code="MISSING_PHONE_NUMBER"
            )

        try:
            # Create Twilio client based on credential type
            api_key_sid = credentials.get("api_key_sid")
            api_key_secret = credentials.get("api_key_secret")
            auth_token = credentials.get("auth_token")

            if api_key_sid and api_key_secret:
                # API Key authentication
                client = Client(api_key_sid, api_key_secret, account_sid)
            elif auth_token:
                # Auth Token authentication
                client = Client(account_sid, auth_token)
            else:
                raise SubscriptionError(
                    message="Missing authentication credentials",
                    error_code="MISSING_CREDENTIALS"
                )
            phone_number = client.incoming_phone_numbers(phone_number_sid).fetch()

            # Build webhook URLs with event_type query parameter
            update_params = {}

            # Configure SMS webhooks
            if "sms_incoming" in events:
                update_params["sms_url"] = f"{endpoint}?event_type=sms_incoming"
                update_params["sms_method"] = "POST"

            if "sms_status" in events:
                update_params["status_callback"] = f"{endpoint}?event_type=sms_status"
                update_params["status_callback_method"] = "POST"

            # Configure Voice webhooks
            voice_events = {
                "voice_incoming",
                "voice_call_status",
                "call_answered",
                "call_completed",
                "voice_answered",
                "voice_completed",
                "voice_initiated",
                "voice_ringing",
            }
            if any(event in events for event in voice_events):
                if "voice_incoming" in events:
                    update_params["voice_url"] = f"{endpoint}?event_type={VOICE_INCOMING_EVENT_TYPE}"
                    update_params["voice_method"] = "POST"

                # All voice status events use the same callback
                if any(
                    e
                    in events
                    for e in {
                        "voice_call_status",
                        "call_answered",
                        "call_completed",
                        "voice_answered",
                        "voice_completed",
                        "voice_initiated",
                        "voice_ringing",
                    }
                ):
                    update_params["status_callback"] = f"{endpoint}?event_type={VOICE_STATUS_EVENT_TYPE}"
                    update_params["status_callback_method"] = "POST"
                    # Note: status_callback_event cannot be set via IncomingPhoneNumber API
                    # Users must configure "Call Status Changes" in Twilio Console
                    # or use TwiML <Dial statusCallbackEvent="..."> for individual calls

            # Configure Recording webhooks
            if "recording_completed" in events:
                # Note: Recording callbacks are configured per-call via TwiML or API
                # We'll add this to properties for documentation
                pass

            # Configure WhatsApp webhooks (if applicable)
            # Note: WhatsApp uses same webhook as SMS for incoming messages

            # Update phone number configuration
            if update_params:
                client.incoming_phone_numbers(phone_number_sid).update(**update_params)

            # Calculate expiration (30 days)
            expires_at = int(time.time()) + (30 * 24 * 3600)

            # Store auth_token only if using auth token authentication
            # (needed for webhook signature validation)
            properties = {
                "phone_number_sid": phone_number_sid,
                "phone_number": phone_number.phone_number,
                "events": events,
                "webhook_urls": update_params
            }

            if auth_token:
                properties["auth_token"] = auth_token

            return Subscription(
                endpoint=endpoint,
                expires_at=expires_at,
                parameters=parameters,
                properties=properties
            )

        except Exception as e:
            raise SubscriptionError(
                message=f"Failed to create Twilio webhook: {str(e)}",
                error_code="WEBHOOK_CREATION_FAILED",
                external_response={"error": str(e)}
            )

    def _delete_subscription(
        self,
        subscription: Subscription,
        credentials: dict[str, Any],
        credential_type: CredentialType,
    ) -> UnsubscribeResult:
        """
        Delete Twilio webhook subscription by clearing phone number webhooks.

        Args:
            subscription: Subscription to delete
            credentials: Twilio credentials (auth_token or api_key)
            credential_type: Credential type

        Returns:
            UnsubscribeResult indicating success/failure
        """
        account_sid = credentials.get("account_sid")
        phone_number_sid = subscription.properties.get("phone_number_sid")

        if not phone_number_sid:
            return UnsubscribeResult(
                success=False,
                message="Missing phone_number_sid in subscription properties"
            )

        try:
            # Create Twilio client based on credential type
            api_key_sid = credentials.get("api_key_sid")
            api_key_secret = credentials.get("api_key_secret")
            auth_token = credentials.get("auth_token")

            if api_key_sid and api_key_secret:
                client = Client(api_key_sid, api_key_secret, account_sid)
            elif auth_token:
                client = Client(account_sid, auth_token)
            else:
                return UnsubscribeResult(
                    success=False,
                    message="Missing authentication credentials"
                )

            # Clear webhook URLs
            client.incoming_phone_numbers(phone_number_sid).update(
                sms_url="",
                voice_url="",
                status_callback=""
            )

            return UnsubscribeResult(
                success=True,
                message=f"Successfully removed webhooks from phone number {phone_number_sid}"
            )

        except Exception as e:
            # Don't fail if phone number is already deleted
            if "not found" in str(e).lower():
                return UnsubscribeResult(
                    success=True,
                    message=f"Phone number {phone_number_sid} not found (may have been deleted)"
                )

            raise UnsubscribeError(
                message=f"Failed to delete Twilio webhook: {str(e)}",
                error_code="WEBHOOK_DELETION_FAILED"
            )

    def _refresh_subscription(
        self,
        subscription: Subscription,
        credentials: dict[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        """
        Refresh Twilio subscription by extending expiration.

        Twilio webhooks don't need refresh on their side, we just update expiration.

        Args:
            subscription: Existing subscription
            credentials: Twilio credentials
            credential_type: Credential type

        Returns:
            Updated subscription with new expiration
        """
        # Extend expiration by 30 days
        new_expires_at = int(time.time()) + (30 * 24 * 3600)

        subscription.expires_at = new_expires_at
        return subscription

    def _fetch_parameter_options(
        self,
        parameter: str,
        credentials: dict[str, Any],
        credential_type: CredentialType,
    ) -> list[ParameterOption]:
        """
        Fetch dynamic parameter options (phone numbers).

        Args:
            parameter: Parameter name ("phone_number_sid")
            credentials: Twilio credentials (auth_token or api_key)
            credential_type: Credential type

        Returns:
            List of available phone numbers
        """
        if parameter == "phone_number_sid":
            return self._fetch_phone_numbers(credentials)

        return []

    def _fetch_phone_numbers(
        self,
        credentials: dict[str, Any]
    ) -> list[ParameterOption]:
        """
        Fetch available Twilio phone numbers for the account.

        Args:
            credentials: Twilio credentials (auth_token or api_key)

        Returns:
            List of ParameterOption with phone numbers
        """
        try:
            account_sid = credentials.get("account_sid")
            api_key_sid = credentials.get("api_key_sid")
            api_key_secret = credentials.get("api_key_secret")
            auth_token = credentials.get("auth_token")

            # Create Twilio client based on credential type
            if api_key_sid and api_key_secret:
                client = Client(api_key_sid, api_key_secret, account_sid)
            elif auth_token:
                client = Client(account_sid, auth_token)
            else:
                return []
            phone_numbers = client.incoming_phone_numbers.list(limit=100)

            options = []
            for pn in phone_numbers:
                label_text = f"{pn.friendly_name} ({pn.phone_number})"

                options.append(
                    ParameterOption(
                        value=pn.sid,
                        label=I18nObject(
                            en_US=label_text,
                            zh_Hans=label_text,
                            ja_JP=label_text
                        )
                    )
                )

            return options

        except Exception as e:
            # Return empty list on error (will show in UI)
            return []

    # OAuth Constants
    _AUTH_URL = "https://www.twilio.com/oauth/authorize"
    _TOKEN_URL = "https://www.twilio.com/oauth/v1/token"
    _API_ACCOUNT_URL = "https://api.twilio.com/2010-04-01/Accounts.json"

    def _oauth_get_authorization_url(
        self, redirect_uri: str, system_credentials: dict[str, Any]
    ) -> str:
        """
        Generate Twilio OAuth authorization URL.

        Args:
            redirect_uri: OAuth callback URL
            system_credentials: Client credentials (client_id, client_secret, scope)

        Returns:
            Authorization URL for user to visit
        """
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "redirect_uri": redirect_uri,
            "scope": system_credentials.get("scope", "openid profile email"),
            "state": state,
            "response_type": "code",
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: dict[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        """
        Exchange authorization code for access token.

        Args:
            redirect_uri: OAuth callback URL
            system_credentials: Client credentials
            request: HTTP request with authorization code

        Returns:
            TriggerOAuthCredentials with access_token and refresh_token

        Raises:
            TriggerProviderOAuthError: If OAuth flow fails
        """
        code = request.args.get("code")
        if not code:
            raise TriggerProviderOAuthError("No authorization code provided")

        if not system_credentials.get("client_id") or not system_credentials.get("client_secret"):
            raise TriggerProviderOAuthError("Client ID or Client Secret is required")

        # Exchange code for tokens
        data = {
            "grant_type": "authorization_code",
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            response_json = response.json()

            access_token = response_json.get("access_token")
            refresh_token = response_json.get("refresh_token")

            if not access_token:
                error_desc = response_json.get("error_description", "Unknown error")
                raise TriggerProviderOAuthError(f"Twilio OAuth failed: {error_desc}")

            # Build credentials dict
            credentials = {
                "access_token": access_token,
            }
            if refresh_token:
                credentials["refresh_token"] = refresh_token

            # Twilio access tokens typically expire in 1 hour (3600 seconds)
            expires_in = response_json.get("expires_in", 3600)
            expires_at = int(time.time()) + expires_in

            return TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)

        except requests.RequestException as e:
            raise TriggerProviderOAuthError(f"Failed to exchange OAuth code: {str(e)}")
        except Exception as e:
            raise TriggerProviderOAuthError(f"Unexpected OAuth error: {str(e)}")
