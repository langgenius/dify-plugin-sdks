from __future__ import annotations

import json
import secrets
import time
import urllib.parse
import uuid
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


class GoogleDriveTrigger(Trigger):
    """Validate Google Drive webhook headers and dispatch change events."""

    _EVENT_NAME = "drive_change_detected"

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        if request.method not in {"POST", "GET"}:
            return EventDispatch(events=[], response=self._ok_response())

        headers = {
            key: request.headers.get(key)
            for key in (
                "X-Goog-Channel-ID",
                "X-Goog-Channel-Token",
                "X-Goog-Message-Number",
                "X-Goog-Resource-ID",
                "X-Goog-Resource-State",
                "X-Goog-Resource-URI",
            )
        }

        channel_id = headers.get("X-Goog-Channel-ID")
        resource_id = headers.get("X-Goog-Resource-ID")
        resource_state = (headers.get("X-Goog-Resource-State") or "").lower()
        channel_token = headers.get("X-Goog-Channel-Token")

        expected_channel = subscription.properties.get("channel_id")
        expected_resource = subscription.properties.get("resource_id")
        expected_token = subscription.properties.get("channel_token")

        if expected_channel and channel_id and expected_channel != channel_id:
            raise TriggerValidationError("Mismatched channel ID in Google Drive notification")

        if expected_resource and resource_id and expected_resource != resource_id:
            raise TriggerValidationError("Mismatched resource ID in Google Drive notification")

        if expected_token and channel_token and expected_token != channel_token:
            raise TriggerValidationError("Invalid channel token for Google Drive notification")

        body = request.get_json(silent=True)
        if body and not isinstance(body, Mapping):
            raise TriggerDispatchError("Invalid JSON payload for Google Drive webhook")

        request.environ["google_drive.trigger.headers"] = {k: v for k, v in headers.items() if v is not None}
        if isinstance(body, Mapping):
            request.environ["google_drive.trigger.body"] = body

        # Google sends an initial sync notification that does not represent changes
        if resource_state == "sync":
            return EventDispatch(events=[], response=self._ok_response())

        event_name = subscription.properties.get("event_name", self._EVENT_NAME)
        return EventDispatch(events=[event_name], response=self._ok_response())

    @staticmethod
    def _ok_response() -> Response:
        return Response(response=json.dumps({"status": "ok"}), mimetype="application/json", status=200)


class GoogleDriveSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Manage Google Drive change notification channels."""

    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _ABOUT_URL = "https://www.googleapis.com/drive/v3/about"
    _START_PAGE_TOKEN_URL = "https://www.googleapis.com/drive/v3/changes/startPageToken"
    _WATCH_URL = "https://www.googleapis.com/drive/v3/changes/watch"
    _STOP_URL = "https://www.googleapis.com/drive/v3/channels/stop"
    _DEFAULT_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        raise TriggerProviderCredentialValidationError("Google Drive trigger only supports OAuth credentials.")

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        client_id = system_credentials.get("client_id")
        if not client_id:
            raise TriggerProviderOAuthError("Client ID is required to start Google Drive OAuth flow")

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
        except requests.RequestException as exc:
            raise TriggerProviderOAuthError(f"Failed to exchange authorization code: {exc}") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise TriggerProviderOAuthError(
                f"Failed to obtain Google Drive OAuth tokens: {payload.get('error_description') or payload}"
            )

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if not access_token or not refresh_token:
            raise TriggerProviderOAuthError("OAuth response does not contain access_token or refresh_token")

        expires_at = int(time.time()) + int(expires_in) if expires_in else -1
        profile = self._fetch_about(access_token)

        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": payload.get("scope", self._DEFAULT_SCOPE),
            "token_type": payload.get("token_type", "Bearer"),
            "user": profile.get("user", {}),
        }

        return TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise TriggerProviderOAuthError("Refresh token is required to renew Google Drive access token")

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            raise TriggerProviderOAuthError("Client ID and Client Secret are required to refresh Google Drive tokens")

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(self._TOKEN_URL, data=data, timeout=10)
        except requests.RequestException as exc:
            raise TriggerProviderOAuthError(f"Failed to refresh Google Drive OAuth token: {exc}") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise TriggerProviderOAuthError(
                f"Unable to refresh Google Drive OAuth token: {payload.get('error_description') or payload}"
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
            raise SubscriptionError("Google Drive trigger requires OAuth credentials", error_code="OAUTH_REQUIRED")

        access_token = credentials.get("access_token")
        if not access_token:
            raise SubscriptionError("Missing Google Drive OAuth access token", error_code="MISSING_ACCESS_TOKEN")

        spaces = self._normalize_spaces(parameters.get("spaces"))
        if not spaces:
            raise SubscriptionError("At least one Drive space must be selected", error_code="SPACES_REQUIRED")

        lifetime = self._safe_lifetime(parameters.get("lifetime_seconds"))
        start_page_token = self._fetch_start_page_token(access_token, spaces)

        channel_id = str(uuid.uuid4())
        channel_token = secrets.token_urlsafe(24)

        watch_body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": endpoint,
            "token": channel_token,
            "payload": True,
        }
        if lifetime:
            watch_body["params"] = {"ttl": str(lifetime)}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "pageToken": start_page_token,
            "spaces": ",".join(spaces),
            "supportsAllDrives": "true",
        }

        try:
            response = requests.post(self._WATCH_URL, headers=headers, params=params, json=watch_body, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(
                f"Network error while creating Google Drive watch: {exc}", error_code="NETWORK_ERROR"
            ) from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise SubscriptionError(
                f"Failed to create Google Drive watch: {payload.get('error', payload)}",
                error_code="WATCH_CREATION_FAILED",
                external_response=payload,
            )

        resource_id = payload.get("resourceId")
        expiration = payload.get("expiration")
        expires_at = int(int(expiration) / 1000) if expiration else -1

        properties: dict[str, Any] = {
            "channel_id": channel_id,
            "resource_id": resource_id,
            "channel_token": channel_token,
            "watch_expiration": expiration,
            "start_page_token": start_page_token,
            "spaces": spaces,
            "event_name": GoogleDriveTrigger._EVENT_NAME,
            "user": credentials.get("user"),
        }

        if lifetime:
            properties["channel_ttl"] = lifetime

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
            raise UnsubscribeError("Google Drive trigger requires OAuth credentials to unsubscribe", error_code="OAUTH_REQUIRED")

        access_token = credentials.get("access_token")
        if not access_token:
            raise UnsubscribeError("Missing Google Drive OAuth access token", error_code="MISSING_ACCESS_TOKEN")

        channel_id = subscription.properties.get("channel_id")
        resource_id = subscription.properties.get("resource_id")
        if not channel_id or not resource_id:
            raise UnsubscribeError("Subscription does not contain channel metadata", error_code="MISSING_CHANNEL")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        body = {"id": channel_id, "resourceId": resource_id}

        try:
            response = requests.post(self._STOP_URL, headers=headers, json=body, timeout=10)
        except requests.RequestException as exc:
            raise UnsubscribeError(
                f"Network error while stopping Google Drive watch: {exc}", error_code="NETWORK_ERROR"
            ) from exc

        if response.status_code in {200, 204}:
            return UnsubscribeResult(success=True, message="Google Drive watch channel stopped successfully")

        payload = response.json() if response.content else {}
        raise UnsubscribeError(
            f"Failed to stop Google Drive watch: {payload.get('error', payload)}",
            error_code="WATCH_STOP_FAILED",
            external_response=payload,
        )

    def _refresh_subscription(
        self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> Subscription:
        parameters = dict(subscription.parameters or {})
        return self._create_subscription(
            endpoint=subscription.endpoint,
            parameters=parameters,
            credentials=credentials,
            credential_type=credential_type,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_about(self, access_token: str) -> Mapping[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"fields": "user"}
        try:
            response = requests.get(self._ABOUT_URL, headers=headers, params=params, timeout=10)
        except requests.RequestException as exc:
            raise TriggerProviderOAuthError(f"Failed to fetch Google Drive profile: {exc}") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise TriggerProviderOAuthError(
                f"Unable to fetch Google Drive profile: {payload.get('error', payload)}"
            )
        return payload

    def _fetch_start_page_token(self, access_token: str, spaces: Sequence[str]) -> str:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"spaces": ",".join(spaces)}
        try:
            response = requests.get(self._START_PAGE_TOKEN_URL, headers=headers, params=params, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(
                f"Network error while fetching startPageToken: {exc}", error_code="NETWORK_ERROR"
            ) from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise SubscriptionError(
                f"Failed to fetch startPageToken: {payload.get('error', payload)}",
                error_code="START_TOKEN_FAILED",
                external_response=payload,
            )

        token = payload.get("startPageToken")
        if not token:
            raise SubscriptionError("startPageToken not present in response", error_code="START_TOKEN_MISSING")
        return str(token)

    @staticmethod
    def _normalize_spaces(raw: Any) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(raw, Sequence):
            normalized: list[str] = []
            for item in raw:
                if isinstance(item, str) and item.strip():
                    normalized.append(item.strip())
            return normalized
        raise SubscriptionError("spaces must be a string or list of strings", error_code="INVALID_SPACES")

    @staticmethod
    def _safe_lifetime(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            lifetime = int(value)
        except (TypeError, ValueError):
            raise SubscriptionError("lifetime_seconds must be a number", error_code="INVALID_LIFETIME")
        if lifetime <= 0:
            raise SubscriptionError("lifetime_seconds must be positive", error_code="INVALID_LIFETIME")
        # Drive API enforces max ~7 days (604800 seconds)
        return min(lifetime, 604800)
