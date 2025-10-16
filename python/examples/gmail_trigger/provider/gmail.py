from __future__ import annotations

import base64
import json
import time
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any

import requests
from werkzeug import Request, Response

from dify_plugin.entities.oauth import OAuthCredentials, TriggerOAuthCredentials
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


class GmailTrigger(Trigger):
    """Dispatch Gmail Pub/Sub push notifications to events."""

    _EVENT_NAME = "gmail_new_email"

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        """Validate and route incoming Pub/Sub push notifications."""
        if request.method != "POST":
            return EventDispatch(events=[], response=self._ok_response())

        envelope = self._parse_envelope(request)
        if not envelope:
            return EventDispatch(events=[], response=self._ok_response())

        message = envelope.get("message") or {}
        data_b64 = message.get("data")
        if not data_b64:
            # Verification pings from Pub/Sub do not include a data payload
            return EventDispatch(events=[], response=self._ok_response())

        attributes: Mapping[str, Any] = message.get("attributes") or {}
        verification_token = subscription.properties.get("verification_token")
        if verification_token and attributes.get("token") != verification_token:
            raise TriggerValidationError("Invalid verification token received from Pub/Sub push request")

        payload = self._decode_payload(data_b64)
        request.environ["gmail.trigger.payload"] = payload
        request.environ["gmail.trigger.attributes"] = dict(attributes)

        event_name = subscription.properties.get("event_name", self._EVENT_NAME)
        return EventDispatch(events=[event_name], response=self._ok_response())

    @staticmethod
    def _parse_envelope(request: Request) -> Mapping[str, Any]:
        try:
            envelope = request.get_json(silent=True)
        except Exception as exc:  # pragma: no cover - defensive path
            raise TriggerDispatchError(f"Failed to parse Pub/Sub payload: {exc}") from exc

        if not isinstance(envelope, Mapping):
            raise TriggerDispatchError("Invalid Pub/Sub envelope received")

        return envelope

    @staticmethod
    def _decode_payload(data_b64: str) -> Mapping[str, Any]:
        try:
            decoded = base64.b64decode(data_b64).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            raise TriggerDispatchError("Unable to decode Pub/Sub message data") from exc

        if not isinstance(payload, Mapping):
            raise TriggerDispatchError("Pub/Sub message data is not a JSON object")

        return payload

    @staticmethod
    def _ok_response() -> Response:
        return Response(response=json.dumps({"status": "ok"}), mimetype="application/json", status=200)


class GmailSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Create and manage Gmail watch subscriptions via the Gmail API."""

    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
    _WATCH_URL = "https://gmail.googleapis.com/gmail/v1/users/me/watch"
    _STOP_URL = "https://gmail.googleapis.com/gmail/v1/users/me/stop"
    _DEFAULT_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        raise TriggerProviderCredentialValidationError("Gmail trigger does not support API key authentication.")

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        client_id = system_credentials.get("client_id")
        if not client_id:
            raise TriggerProviderOAuthError("Client ID is required to start Gmail OAuth flow")

        scope = system_credentials.get("scope", self._DEFAULT_SCOPE)
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        code = request.args.get("code")
        if not code:
            raise TriggerProviderOAuthError("Missing authorization code in callback request")

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise TriggerProviderOAuthError("Client ID and Client Secret are required")

        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(self._TOKEN_URL, data=data, timeout=10)
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise TriggerProviderOAuthError(f"Failed to exchange authorization code: {exc}") from exc

        payload = response.json()
        if response.status_code != 200:
            raise TriggerProviderOAuthError(
                f"Failed to obtain Gmail OAuth tokens: {payload.get('error_description') or payload}"
            )

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if not access_token or not refresh_token:
            raise TriggerProviderOAuthError("OAuth response does not contain access_token or refresh_token")

        expires_at = int(time.time()) + int(expires_in) if expires_in else -1

        metadata = self._fetch_profile(access_token)
        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": payload.get("scope", self._DEFAULT_SCOPE),
            "token_type": payload.get("token_type", "Bearer"),
            "email": metadata.get("emailAddress"),
        }

        return TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise TriggerProviderOAuthError("Refresh token is required to renew Gmail access token")

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise TriggerProviderOAuthError("Client ID and Client Secret are required to refresh Gmail tokens")

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(self._TOKEN_URL, data=data, timeout=10)
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise TriggerProviderOAuthError(f"Failed to refresh Gmail OAuth token: {exc}") from exc

        payload = response.json()
        if response.status_code != 200:
            raise TriggerProviderOAuthError(
                f"Unable to refresh Gmail OAuth token: {payload.get('error_description') or payload}"
            )

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not access_token:
            raise TriggerProviderOAuthError("Refresh response does not contain access_token")

        expires_at = int(time.time()) + int(expires_in) if expires_in else -1

        refreshed_credentials = {
            **credentials,
            "access_token": access_token,
            "scope": payload.get("scope", credentials.get("scope", self._DEFAULT_SCOPE)),
            "token_type": payload.get("token_type", credentials.get("token_type", "Bearer")),
        }

        return OAuthCredentials(credentials=refreshed_credentials, expires_at=expires_at)

    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        if credential_type != CredentialType.OAUTH:
            raise SubscriptionError("Gmail trigger requires OAuth credentials", error_code="OAUTH_REQUIRED")

        access_token = credentials.get("access_token")
        if not access_token:
            raise SubscriptionError("Missing Gmail OAuth access token", error_code="MISSING_ACCESS_TOKEN")

        topic_name = parameters.get("topic_name")
        if not topic_name:
            raise SubscriptionError("Pub/Sub topic name is required", error_code="TOPIC_REQUIRED")

        label_ids = self._normalize_label_ids(parameters.get("label_ids"))
        label_filter_action = (parameters.get("label_filter_action") or "include").lower()
        if label_filter_action not in {"include", "exclude"}:
            raise SubscriptionError("label_filter_action must be 'include' or 'exclude'", error_code="INVALID_FILTER")

        verification_token = parameters.get("verification_token")

        watch_body: dict[str, Any] = {"topicName": topic_name}
        if label_ids:
            watch_body["labelIds"] = label_ids
        if label_filter_action:
            watch_body["labelFilterAction"] = label_filter_action

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        profile = self._fetch_profile(access_token)

        try:
            response = requests.post(self._WATCH_URL, headers=headers, json=watch_body, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(f"Network error while creating Gmail watch: {exc}", error_code="NETWORK_ERROR") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise SubscriptionError(
                f"Failed to create Gmail watch: {payload.get('error', payload)}",
                error_code="WATCH_CREATION_FAILED",
                external_response=payload,
            )

        history_id = payload.get("historyId")
        expiration = payload.get("expiration")
        expires_at = int(int(expiration) / 1000) if expiration else -1

        properties: dict[str, Any] = {
            "topic_name": topic_name,
            "label_ids": label_ids,
            "label_filter_action": label_filter_action,
            "history_id": history_id,
            "initial_history_id": history_id,
            "watch_expiration": expiration,
            "verification_token": verification_token,
            "email_address": profile.get("emailAddress"),
            "event_name": GmailTrigger._EVENT_NAME,
        }

        return Subscription(
            expires_at=expires_at,
            endpoint=endpoint,
            parameters=parameters,
            properties=properties,
        )

    def _delete_subscription(
        self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> UnsubscribeResult:
        if credential_type != CredentialType.OAUTH:
            raise UnsubscribeError("Gmail trigger requires OAuth credentials to unsubscribe", error_code="OAUTH_REQUIRED")

        access_token = credentials.get("access_token")
        if not access_token:
            raise UnsubscribeError("Missing Gmail OAuth access token", error_code="MISSING_ACCESS_TOKEN")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self._STOP_URL, headers=headers, timeout=10)
        except requests.RequestException as exc:
            raise UnsubscribeError(
                f"Network error while stopping Gmail watch: {exc}",
                error_code="NETWORK_ERROR",
            ) from exc

        if response.status_code in {200, 204}:
            return UnsubscribeResult(success=True, message="Gmail watch channel stopped successfully")

        payload = response.json() if response.content else {}
        raise UnsubscribeError(
            f"Failed to stop Gmail watch: {payload.get('error', payload)}",
            error_code="WATCH_STOP_FAILED",
            external_response=payload,
        )

    def _refresh_subscription(
        self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> Subscription:
        parameters = dict(subscription.parameters or {})
        if subscription.properties.get("verification_token") and "verification_token" not in parameters:
            parameters["verification_token"] = subscription.properties.get("verification_token")

        return self._create_subscription(
            endpoint=subscription.endpoint,
            parameters=parameters,
            credentials=credentials,
            credential_type=credential_type,
        )

    @staticmethod
    def _normalize_label_ids(raw: Any) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [label.strip() for label in raw.split(",") if label.strip()]
        if isinstance(raw, Sequence):
            normalized: list[str] = []
            for item in raw:
                if isinstance(item, str) and item.strip():
                    normalized.append(item.strip())
            return normalized
        raise SubscriptionError("label_ids must be a string or list of strings", error_code="INVALID_LABEL_IDS")

    def _fetch_profile(self, access_token: str) -> Mapping[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(self._PROFILE_URL, headers=headers, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(f"Network error while fetching Gmail profile: {exc}", error_code="NETWORK_ERROR") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise SubscriptionError(
                f"Failed to fetch Gmail profile: {payload.get('error', payload)}",
                error_code="PROFILE_FETCH_FAILED",
                external_response=payload,
            )

        return payload
