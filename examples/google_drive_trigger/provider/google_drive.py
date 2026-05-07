from __future__ import annotations

import contextlib
import json
import secrets
import time
import urllib.parse
import uuid
from collections.abc import Mapping, Sequence
from http import HTTPStatus
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

VALID_WEBHOOK_METHODS = frozenset({"POST", "GET"})
CHANNEL_STOP_SUCCESS_STATUSES = frozenset({HTTPStatus.OK, HTTPStatus.NO_CONTENT})


class GoogleDriveTrigger(Trigger):
    """Validate Google Drive webhook headers and dispatch change events."""

    _EVENT_NAME = "drive_change_detected"
    _STORAGE_KEY = "google-drive-trigger:last-page-token"
    _CHANGES_ENDPOINT = "https://www.googleapis.com/drive/v3/changes"

    def _dispatch_event(
        self, subscription: Subscription, request: Request
    ) -> EventDispatch:
        if request.method not in VALID_WEBHOOK_METHODS:
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
            msg = "Mismatched channel ID in Google Drive notification"
            raise TriggerValidationError(msg)

        if expected_resource and resource_id and expected_resource != resource_id:
            msg = "Mismatched resource ID in Google Drive notification"
            raise TriggerValidationError(msg)

        if expected_token and channel_token and expected_token != channel_token:
            msg = "Invalid channel token for Google Drive notification"
            raise TriggerValidationError(msg)

        body = request.get_json(silent=True)
        if body and not isinstance(body, Mapping):
            msg = "Invalid JSON payload for Google Drive webhook"
            raise TriggerDispatchError(msg)

        request.environ["google_drive.trigger.headers"] = {
            k: v for k, v in headers.items() if v is not None
        }
        if isinstance(body, Mapping):
            request.environ["google_drive.trigger.body"] = body

        # Google sends an initial sync notification that does not represent changes
        if resource_state == "sync":
            return EventDispatch(events=[], response=self._ok_response())

        event_name = subscription.properties.get("event_name", self._EVENT_NAME)

        if not self.runtime.credentials:
            msg = "Missing Google Drive OAuth access token in runtime credentials"
            raise TriggerDispatchError(msg)

        if not subscription.parameters:
            msg = "Missing Google Drive parameters in subscription"
            raise TriggerDispatchError(msg)

        # fetch changes
        changes = self._fetch_changes(
            access_token=self.runtime.credentials.get("access_token") or "",
            spaces=subscription.properties.get("spaces") or [],
            include_removed=subscription.parameters.get("include_removed", False),
            restrict_to_my_drive=subscription.parameters.get(
                "restrict_to_my_drive", False
            ),
            include_items_from_all_drives=subscription.parameters.get(
                "include_items_from_all_drives", False
            ),
            supports_all_drives=subscription.parameters.get(
                "supports_all_drives", False
            ),
            subscription=subscription,
        )

        return EventDispatch(
            events=[event_name],
            response=self._ok_response(),
            payload={"changes": changes},
        )

    def _fetch_changes(
        self,
        access_token: str,
        spaces: Sequence[str],
        include_removed: bool,
        restrict_to_my_drive: bool,
        include_items_from_all_drives: bool,
        supports_all_drives: bool,
        subscription: Subscription,
    ) -> list[dict[str, Any]]:
        """
        Fetch changes from Google Drive.

        This method will fetch changes from Google Drive until the
        nextPageToken is not found.
        It will also set the max_page_token to the storage.

        Args:
            access_token: The access token for Google Drive.
            spaces: The spaces to fetch changes from.
            include_removed: Whether to include removed items.
            restrict_to_my_drive: Whether to restrict to my drive.
            include_items_from_all_drives: Whether to include items from all drives.
            supports_all_drives: Whether to support all drives.
            subscription: The subscription to fetch changes from.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        changes: list[dict[str, Any]] = []

        while True:
            # (FIXME) it may lead some duplicates if frequency is too high
            page_token = self._get_max_page_token(subscription)
            params: dict[str, Any] = {
                "pageToken": page_token,
                "spaces": ",".join(spaces),
                "includeRemoved": str(include_removed).lower(),
                "restrictToMyDrive": str(restrict_to_my_drive).lower(),
                "includeItemsFromAllDrives": str(include_items_from_all_drives).lower(),
                "supportsAllDrives": str(supports_all_drives).lower(),
                "fields": "changes(changeType,removed,fileId,"
                "file(name,id,mimeType,owners,parents,driveId,teamDriveId,trashed,ownedByMe,"
                "modifiedTime,createdTime,webViewLink,iconLink,lastModifyingUser,capabilities)),"
                "newStartPageToken,nextPageToken",
            }

            try:
                response = requests.get(
                    self._CHANGES_ENDPOINT, headers=headers, params=params, timeout=10
                )
            except requests.RequestException as exc:
                msg = f"Failed to fetch Google Drive changes: {exc}"
                raise ValueError(msg) from exc

            payload = response.json() if response.content else {}
            if response.status_code != HTTPStatus.OK:
                msg = f"Google Drive changes API error: {payload}"
                raise ValueError(msg)

            next_page_token = payload.get("nextPageToken")
            new_start_page_token = payload.get("newStartPageToken")

            current_page_token = self._get_max_page_token(subscription)
            if current_page_token == next_page_token:
                # duplicate changes detected, skip the rest of the changes
                break

            raw_changes = payload.get("changes") or []
            if isinstance(raw_changes, Sequence):
                changes.extend(
                    dict(change)
                    for change in raw_changes
                    if isinstance(change, Mapping)
                )

            if next_page_token:
                self._set_max_page_token(next_page_token)

            if new_start_page_token:
                self._set_max_page_token(new_start_page_token)
                break

        return changes

    def _set_max_page_token(self, token: str) -> None:
        """
        Set the maximum page token to the storage.

        If the storage is not found, do nothing.
        """
        with contextlib.suppress(Exception):
            self.runtime.session.storage.set(self._STORAGE_KEY, token.encode())

    def _get_max_page_token(self, subscription: Subscription) -> str:
        """
        Get the maximum page token from the storage.

        If the storage is not found, return 0.

        Returns:
            The return value.
        """
        try:
            return self.runtime.session.storage.get(self._STORAGE_KEY).decode() or "0"
        except Exception:
            return subscription.properties.get("start_page_token") or "0"

    @staticmethod
    def _ok_response() -> Response:
        return Response(
            response=json.dumps({"status": "ok"}),
            mimetype="application/json",
            status=200,
        )


class GoogleDriveSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Manage Google Drive change notification channels."""

    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
    _ABOUT_URL = "https://www.googleapis.com/drive/v3/about"
    _START_PAGE_ENDPOINT = "https://www.googleapis.com/drive/v3/changes/startPageToken"
    _WATCH_URL = "https://www.googleapis.com/drive/v3/changes/watch"
    _STOP_URL = "https://www.googleapis.com/drive/v3/channels/stop"
    _DEFAULT_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly https://www.googleapis.com/auth/drive.appdata"

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        msg = "Google Drive trigger only supports OAuth credentials."
        raise TriggerProviderCredentialValidationError(msg)

    def _oauth_get_authorization_url(
        self, redirect_uri: str, system_credentials: Mapping[str, Any]
    ) -> str:
        client_id = system_credentials.get("client_id")
        if not client_id:
            msg = "Client ID is required to start Google Drive OAuth flow"
            raise TriggerProviderOAuthError(msg)

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
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"{self._AUTH_URL}?{query}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        code = request.args.get("code")
        if not code:
            msg = "Missing authorization code in callback request"
            raise TriggerProviderOAuthError(msg)

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            msg = "Client ID and Client Secret are required"
            raise TriggerProviderOAuthError(msg)

        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(self._OAUTH_ENDPOINT, data=data, timeout=10)
        except requests.RequestException as exc:
            msg = f"Failed to exchange authorization code: {exc}"
            raise TriggerProviderOAuthError(msg) from exc

        payload = response.json() if response.content else {}
        if response.status_code != HTTPStatus.OK:
            error_description = payload.get("error_description") or payload
            msg = f"Failed to obtain Google Drive OAuth tokens: {error_description}"
            raise TriggerProviderOAuthError(msg)

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if not access_token or not refresh_token:
            msg = "OAuth response does not contain access_token or refresh_token"
            raise TriggerProviderOAuthError(msg)

        expires_at = int(time.time()) + int(expires_in) if expires_in else -1
        profile = self._fetch_about(access_token)

        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": payload.get("scope", self._DEFAULT_SCOPE),
            "token_type": payload.get("token_type", "Bearer"),
            "user": json.dumps(profile.get("user", {})),
        }

        return TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)

    def _oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> OAuthCredentials:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            msg = "Refresh token is required to renew Google Drive access token"
            raise TriggerProviderOAuthError(msg)

        client_id = system_credentials.get("client_id")
        client_secret = system_credentials.get("client_secret")
        if not client_id or not client_secret:
            msg = (
                "Client ID and Client Secret are required to refresh "
                "Google Drive tokens"
            )
            raise TriggerProviderOAuthError(msg)

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(self._OAUTH_ENDPOINT, data=data, timeout=10)
        except requests.RequestException as exc:
            msg = f"Failed to refresh Google Drive OAuth token: {exc}"
            raise TriggerProviderOAuthError(msg) from exc

        payload = response.json() if response.content else {}
        if response.status_code != HTTPStatus.OK:
            error_description = payload.get("error_description") or payload
            msg = f"Unable to refresh Google Drive OAuth token: {error_description}"
            raise TriggerProviderOAuthError(msg)

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not access_token:
            msg = "Refresh response does not contain access_token"
            raise TriggerProviderOAuthError(msg)

        expires_at = int(time.time()) + int(expires_in) if expires_in else -1
        refreshed_credentials = {
            **credentials,
            "access_token": access_token,
            "scope": payload.get(
                "scope", credentials.get("scope", self._DEFAULT_SCOPE)
            ),
            "token_type": payload.get(
                "token_type", credentials.get("token_type", "Bearer")
            ),
        }

        return OAuthCredentials(
            credentials=refreshed_credentials, expires_at=expires_at
        )

    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        if credential_type != CredentialType.OAUTH:
            msg = "Google Drive trigger requires OAuth credentials"
            raise SubscriptionError(
                msg,
                error_code="OAUTH_REQUIRED",
            )

        access_token = credentials.get("access_token")
        if not access_token:
            msg = "Missing Google Drive OAuth access token"
            raise SubscriptionError(
                msg,
                error_code="MISSING_ACCESS_TOKEN",
            )

        spaces = self._normalize_spaces(parameters.get("spaces"))
        if not spaces:
            msg = "At least one Drive space must be selected"
            raise SubscriptionError(
                msg,
                error_code="SPACES_REQUIRED",
            )

        start_page_token = self._fetch_start_page_token(access_token, spaces)

        # set the start_page_token to the storage
        self.runtime.session.storage.set(
            GoogleDriveTrigger._STORAGE_KEY, str(start_page_token).encode("utf-8")
        )

        channel_id = str(uuid.uuid4())
        channel_token = secrets.token_urlsafe(24)

        watch_body: dict[str, Any] = {
            "id": channel_id,
            "type": "web_hook",
            "address": endpoint,
            "token": channel_token,
            "payload": True,
            "expiration": int(time.time() * 1000) + (24 * 60 * 60 - 1800) * 1000,
            # add a 1800 seconds buffer to the expiration time to avoid race conditions
        }

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
            response = requests.post(
                self._WATCH_URL,
                headers=headers,
                params=params,
                json=watch_body,
                timeout=10,
            )
        except requests.RequestException as exc:
            msg = f"Network error while creating Google Drive watch: {exc}"
            raise SubscriptionError(
                msg,
                error_code="NETWORK_ERROR",
            ) from exc

        payload = response.json() if response.content else {}
        if response.status_code != HTTPStatus.OK:
            msg = (
                f"Failed to create Google Drive watch: {payload.get('error', payload)}"
            )
            raise SubscriptionError(
                msg,
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
            "user": json.loads(credentials.get("user", "{}")),
        }

        return Subscription(
            expires_at=expires_at,
            endpoint=endpoint,
            parameters=parameters,
            properties=properties,
        )

    def _delete_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> UnsubscribeResult:
        if credential_type != CredentialType.OAUTH:
            msg = "Google Drive trigger requires OAuth credentials to unsubscribe"
            raise UnsubscribeError(
                msg,
                error_code="OAUTH_REQUIRED",
            )

        access_token = credentials.get("access_token")
        if not access_token:
            msg = "Missing Google Drive OAuth access token"
            raise UnsubscribeError(
                msg,
                error_code="MISSING_ACCESS_TOKEN",
            )

        channel_id = subscription.properties.get("channel_id")
        resource_id = subscription.properties.get("resource_id")
        if not channel_id or not resource_id:
            msg = "Subscription does not contain channel metadata"
            raise UnsubscribeError(
                msg,
                error_code="MISSING_CHANNEL",
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        body = {"id": channel_id, "resourceId": resource_id}

        try:
            response = requests.post(
                self._STOP_URL, headers=headers, json=body, timeout=10
            )
        except requests.RequestException as exc:
            msg = f"Network error while stopping Google Drive watch: {exc}"
            raise UnsubscribeError(
                msg,
                error_code="NETWORK_ERROR",
            ) from exc

        if response.status_code in CHANNEL_STOP_SUCCESS_STATUSES:
            return UnsubscribeResult(
                success=True, message="Google Drive watch channel stopped successfully"
            )

        payload = response.json() if response.content else {}
        msg = f"Failed to stop Google Drive watch: {payload.get('error', payload)}"
        raise UnsubscribeError(
            msg,
            error_code="WATCH_STOP_FAILED",
            external_response=payload,
        )

    def _refresh_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
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
            response = requests.get(
                self._ABOUT_URL, headers=headers, params=params, timeout=10
            )
        except requests.RequestException as exc:
            msg = f"Failed to fetch Google Drive profile: {exc}"
            raise TriggerProviderOAuthError(msg) from exc

        payload = response.json() if response.content else {}
        if response.status_code != HTTPStatus.OK:
            msg = (
                f"Unable to fetch Google Drive profile: {payload.get('error', payload)}"
            )
            raise TriggerProviderOAuthError(msg)
        return payload

    def _fetch_start_page_token(self, access_token: str, spaces: Sequence[str]) -> str:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"spaces": ",".join(spaces)}
        try:
            response = requests.get(
                self._START_PAGE_ENDPOINT, headers=headers, params=params, timeout=10
            )
        except requests.RequestException as exc:
            msg = f"Network error while fetching startPageToken: {exc}"
            raise SubscriptionError(
                msg,
                error_code="NETWORK_ERROR",
            ) from exc

        payload = response.json() if response.content else {}
        if response.status_code != HTTPStatus.OK:
            msg = f"Failed to fetch startPageToken: {payload.get('error', payload)}"
            raise SubscriptionError(
                msg,
                error_code="START_TOKEN_FAILED",
                external_response=payload,
            )

        token = payload.get("startPageToken")
        if not token:
            msg = "startPageToken not present in response"
            raise SubscriptionError(
                msg,
                error_code="START_TOKEN_MISSING",
            )
        return str(token)

    @staticmethod
    def _normalize_spaces(raw: object) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(raw, Sequence):
            normalized: list[str] = [
                item.strip() for item in raw if isinstance(item, str) and item.strip()
            ]
            return normalized
        msg = "spaces must be a string or list of strings"
        raise SubscriptionError(msg, error_code="INVALID_SPACES")
