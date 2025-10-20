from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.parse
from typing import Any, Mapping

import requests
from werkzeug import Request, Response

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import TriggerOAuthCredentials, OAuthCredentials
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
    """Handle Gmail Pub/Sub push event dispatch."""

    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        # Optional OIDC verification for Pub/Sub push
        props = subscription.properties or {}
        require_oidc = bool(props.get("require_oidc"))
        oidc_audience = props.get("oidc_audience") or subscription.endpoint
        expected_sa = props.get("oidc_service_account_email")

        auth_header = request.headers.get("Authorization")
        if require_oidc:
            if not auth_header or not auth_header.startswith("Bearer "):
                raise TriggerValidationError("Missing OIDC bearer token for Pub/Sub push")
            token = auth_header.split(" ", 1)[1].strip()
            self._verify_oidc_token(token=token, audience=oidc_audience, expected_email=expected_sa)

        # Parse Pub/Sub push envelope
        try:
            envelope: Mapping[str, Any] = request.get_json(force=True)
        except Exception as exc:
            raise TriggerDispatchError(f"Invalid JSON: {exc}") from exc

        if not isinstance(envelope, Mapping) or "message" not in envelope:
            raise TriggerDispatchError("Missing Pub/Sub message")

        message: Mapping[str, Any] = envelope.get("message") or {}
        data_b64: str | None = message.get("data")
        if not data_b64:
            raise TriggerDispatchError("Missing Pub/Sub message.data")

        try:
            decoded: str = base64.b64decode(data_b64).decode("utf-8")
            notification: dict[str, Any] = json.loads(decoded)
        except Exception as exc:
            raise TriggerDispatchError(f"Invalid Pub/Sub data: {exc}") from exc

        if not notification.get("historyId") or not notification.get("emailAddress"):
            raise TriggerDispatchError("Missing historyId or emailAddress in Gmail notification")

        # Decide concrete events by fetching history delta now, and stash pending batches for events
        # Use runtime credentials (OAuth)
        if not self.runtime or not self.runtime.credentials:
            raise TriggerDispatchError("Missing runtime credentials for Gmail API")
        access_token = self.runtime.credentials.get("access_token")
        if not access_token:
            raise TriggerDispatchError("Missing access_token for Gmail API")

        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
        user_id: str = (subscription.properties or {}).get("watch_email") or "me"

        # Storage keys
        sub_key = (subscription.properties or {}).get("subscription_key") or ""
        checkpoint_key = f"gmail:{sub_key}:history_checkpoint"
        pending_added_key = f"gmail:{sub_key}:pending:message_added"
        pending_deleted_key = f"gmail:{sub_key}:pending:message_deleted"
        pending_label_added_key = f"gmail:{sub_key}:pending:label_added"
        pending_label_removed_key = f"gmail:{sub_key}:pending:label_removed"

        session = self.runtime.session

        # If first time: initialize checkpoint and return 200 without events
        if not session.storage.exist(checkpoint_key):
            session.storage.set(checkpoint_key, str(notification["historyId"]).encode("utf-8"))
            response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")
            return EventDispatch(events=[], response=response)

        start_history_id: str = session.storage.get(checkpoint_key).decode("utf-8")

        # Fetch history delta
        history_url: str = f"{self._GMAIL_BASE}/users/{user_id}/history"
        params: dict[str, Any] = {
            "startHistoryId": start_history_id,
        }

        added: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []
        labels_added: list[dict[str, Any]] = []
        labels_removed: list[dict[str, Any]] = []

        try:
            while True:
                resp: requests.Response = requests.get(history_url, headers=headers, params=params, timeout=10)
                if resp.status_code != 200:
                    # If historyId invalid/out-of-date → reset checkpoint to current and return no events
                    try:
                        err: dict[str, Any] = resp.json()
                        reason = (err.get("error", {}).get("errors", [{}])[0].get("reason")) or err.get(
                            "error", {}
                        ).get("status")
                    except Exception:
                        reason = ""
                    session.storage.set(checkpoint_key, str(notification["historyId"]).encode("utf-8"))
                    response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")
                    return EventDispatch(events=[], response=response)

                data: dict[str, Any] = resp.json() or {}
                for h in data.get("history", []) or []:
                    for item in h.get("messagesAdded", []) or []:
                        msg = item.get("message") or {}
                        if msg.get("id"):
                            added.append({"id": msg.get("id"), "threadId": msg.get("threadId")})
                    for item in h.get("messagesDeleted", []) or []:
                        msg = item.get("message") or {}
                        if msg.get("id"):
                            deleted.append({"id": msg.get("id"), "threadId": msg.get("threadId")})
                    for item in h.get("labelsAdded", []) or []:
                        msg = item.get("message") or {}
                        if msg.get("id"):
                            labels_added.append(
                                {
                                    "id": msg.get("id"),
                                    "threadId": msg.get("threadId"),
                                    "labelIds": item.get("labelIds") or [],
                                }
                            )
                    for item in h.get("labelsRemoved", []) or []:
                        msg = item.get("message") or {}
                        if msg.get("id"):
                            labels_removed.append(
                                {
                                    "id": msg.get("id"),
                                    "threadId": msg.get("threadId"),
                                    "labelIds": item.get("labelIds") or [],
                                }
                            )

                page_token = data.get("nextPageToken")
                if not page_token:
                    break
                params["pageToken"] = page_token
        finally:
            # Advance checkpoint to current notification's historyId regardless of content
            session.storage.set(checkpoint_key, str(notification["historyId"]).encode("utf-8"))

        # Stash pending batches per event family
        events: list[str] = []

        def _stash(key: str, items: list[dict[str, Any]], event_name: str) -> None:
            nonlocal events
            if not items:
                return
            payload = json.dumps({"historyId": notification["historyId"], "items": items}).encode("utf-8")
            session.storage.set(key, payload)
            events.append(event_name)

        _stash(pending_added_key, added, "gmail_message_added")
        _stash(pending_deleted_key, deleted, "gmail_message_deleted")
        _stash(pending_label_added_key, labels_added, "gmail_label_added")
        _stash(pending_label_removed_key, labels_removed, "gmail_label_removed")

        response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")
        return EventDispatch(events=events, response=response)

    def _verify_oidc_token(self, token: str, audience: str, expected_email: str | None = None) -> None:
        """Verify OIDC token from Pub/Sub push using google-auth if available.

        If google-auth is not installed, and verification is required, raise TriggerValidationError.
        """
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            req = google_requests.Request()
            claims = id_token.verify_oauth2_token(token, req, audience=audience)
            issuer = claims.get("iss")
            if issuer not in ("https://accounts.google.com", "accounts.google.com"):
                raise TriggerValidationError("Invalid OIDC token issuer")
            if expected_email and claims.get("email") != expected_email:
                raise TriggerValidationError("OIDC token service account email mismatch")
        except ImportError as exc:
            raise TriggerValidationError("google-auth is required for OIDC verification but not installed") from exc
        except Exception as exc:  # pragma: no cover - verification failure
            # id_token.verify_oauth2_token raises on invalid signature/audience/etc.
            raise TriggerValidationError(f"OIDC verification failed: {exc}") from exc


class GmailSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Manage Gmail trigger subscriptions (watch/stop/refresh, OAuth)."""

    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    _DEFAULT_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        """Gmail trigger does not support API Key credentials.

        Raise a friendly validation error to guide users to OAuth.
        """
        raise TriggerProviderCredentialValidationError(
            "Gmail trigger does not support API Key credentials. Please use OAuth authorization."
        )

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self._DEFAULT_SCOPE,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        code = request.args.get("code")
        if not code:
            raise TriggerProviderOAuthError("No code provided")

        if not system_credentials.get("client_id") or not system_credentials.get("client_secret"):
            raise TriggerProviderOAuthError("Client ID or Client Secret is required")

        data: dict[str, str] = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp: requests.Response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        payload: dict[str, Any] = resp.json()
        access_token: str | None = payload.get("access_token")
        if not access_token:
            raise TriggerProviderOAuthError(f"Error in Google OAuth: {payload}")

        expires_in: int = int(payload.get("expires_in") or 0)
        refresh_token: str | None = payload.get("refresh_token")
        expires_at: int = int(time.time()) + expires_in if expires_in else -1
        credentials: dict[str, str] = {"access_token": access_token}
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        return TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise TriggerProviderOAuthError("Missing refresh_token for OAuth refresh")

        data: dict[str, str] = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp: requests.Response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        payload: dict[str, Any] = resp.json()
        access_token: str | None = payload.get("access_token")
        if not access_token:
            raise TriggerProviderOAuthError(f"OAuth refresh failed: {payload}")

        expires_in: int = int(payload.get("expires_in") or 0)
        expires_at: int = int(time.time()) + expires_in if expires_in else -1
        refreshed: dict[str, str] = {"access_token": access_token}
        if refresh_token:
            refreshed["refresh_token"] = refresh_token
        return OAuthCredentials(credentials=refreshed, expires_at=expires_at)

    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        watch_email: str = parameters.get("watch_email") or "me"
        topic_name: str | None = parameters.get("topic_name")
        if not topic_name:
            raise ValueError("topic_name is required (projects/<project>/topics/<topic>)")
        label_ids: list[str] = parameters.get("label_ids") or []
        label_filter_action: str | None = parameters.get("label_filter_action")

        access_token: str | None = credentials.get("access_token")
        if not access_token:
            raise SubscriptionError("Missing access_token for Gmail API")

        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body: dict[str, Any] = {"topicName": topic_name}
        if label_ids:
            body["labelIds"] = label_ids
        if label_filter_action in ("include", "exclude"):
            body["labelFilterAction"] = label_filter_action

        url = f"{self._GMAIL_BASE}/users/{urllib.parse.quote(watch_email)}/watch"
        try:
            resp: requests.Response = requests.post(url, headers=headers, json=body, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(
                f"Network error while calling users.watch: {exc}", error_code="NETWORK_ERROR"
            ) from exc

        if resp.status_code not in (200, 201):
            try:
                err: dict[str, Any] = resp.json()
            except Exception:
                err = {"message": resp.text}
            raise SubscriptionError(
                f"Failed to create Gmail watch: {err}",
                error_code="WATCH_CREATION_FAILED",
                external_response=err if isinstance(err, dict) else None,
            )

        data: dict[str, Any] = resp.json() or {}
        start_history_id: str | None = data.get("historyId")
        expiration_ms: int | None = data.get("expiration")  # may not be present
        # Gmail watch is time-limited; if expiration is not provided, use 6 days as a safe default
        expires_at: int = int(expiration_ms / 1000) if expiration_ms else int(time.time()) + 6 * 24 * 60 * 60

        # OIDC expectations for trigger dispatch (optional)
        require_oidc: bool = bool(parameters.get("require_oidc") or False)
        oidc_audience: str = parameters.get("oidc_audience") or endpoint
        oidc_sa_email: str | None = parameters.get("oidc_service_account_email")

        properties: dict[str, Any] = {
            "watch_email": watch_email,
            "topic_name": topic_name,
            "label_ids": label_ids,
            "label_filter_action": label_filter_action,
            "start_history_id": start_history_id,
            "require_oidc": require_oidc,
            "oidc_audience": oidc_audience,
        }
        if oidc_sa_email:
            properties["oidc_service_account_email"] = oidc_sa_email

        # internal subscription key for storage scoping
        import uuid as _uuid

        properties["subscription_key"] = _uuid.uuid4().hex

        return Subscription(
            expires_at=expires_at,
            endpoint=endpoint,
            parameters=parameters,
            properties=properties,
        )

    def _delete_subscription(
        self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> UnsubscribeResult:
        access_token: str | None = credentials.get("access_token")
        if not access_token:
            raise UnsubscribeError("Missing access_token for Gmail API", error_code="MISSING_CREDENTIALS")

        watch_email: str = (subscription.properties or {}).get("watch_email") or "me"
        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        url: str = f"{self._GMAIL_BASE}/users/{urllib.parse.quote(watch_email)}/stop"

        try:
            resp: requests.Response = requests.post(url, headers=headers, json={}, timeout=10)
        except requests.RequestException as exc:
            return UnsubscribeResult(success=False, message=f"Network error: {exc}")

        if resp.status_code in (200, 204):
            return UnsubscribeResult(success=True, message="Gmail watch stopped")

        try:
            err: dict[str, Any] = resp.json()
        except Exception:
            err = {"message": resp.text}
        return UnsubscribeResult(success=False, message=f"Failed to stop Gmail watch: {err}")

    def _refresh_subscription(
        self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> Subscription:
        # Re-issue users.watch with previous parameters
        access_token = credentials.get("access_token")
        if not access_token:
            raise SubscriptionError("Missing access_token for Gmail API", error_code="MISSING_CREDENTIALS")

        watch_email: str = (subscription.properties or {}).get("watch_email") or "me"
        topic_name: str | None = (subscription.properties or {}).get("topic_name")
        label_ids: list[str] = (subscription.properties or {}).get("label_ids") or []
        label_filter_action: str | None = (subscription.properties or {}).get("label_filter_action")

        if not topic_name:
            raise SubscriptionError("Missing topic_name in subscription properties", error_code="INVALID_PROPERTIES")

        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body: dict[str, Any] = {"topicName": topic_name}
        if label_ids:
            body["labelIds"] = label_ids
        if label_filter_action in ("include", "exclude"):
            body["labelFilterAction"] = label_filter_action

        url = f"{self._GMAIL_BASE}/users/{urllib.parse.quote(watch_email)}/watch"
        resp: requests.Response = requests.post(url, headers=headers, json=body, timeout=10)
        if resp.status_code not in (200, 201):
            try:
                err: dict[str, Any] = resp.json()
            except Exception:
                err = {"message": resp.text}
            raise SubscriptionError(
                f"Failed to refresh Gmail watch: {err}", error_code="WATCH_REFRESH_FAILED", external_response=err
            )

        data: dict[str, Any] = resp.json() or {}
        start_history_id: str | None = data.get("historyId")
        expiration_ms: int | None = data.get("expiration")
        expires_at: int = int(expiration_ms / 1000) if expiration_ms else int(time.time()) + 6 * 24 * 60 * 60

        properties: dict[str, Any] = dict(subscription.properties or {})
        if start_history_id:
            properties["start_history_id"] = start_history_id

        return Subscription(
            expires_at=expires_at,
            endpoint=subscription.endpoint,
            properties=properties,
        )

    def _fetch_parameter_options(
        self, parameter: str, credentials: Mapping[str, Any], credential_type: CredentialType
    ) -> list[ParameterOption]:
        if parameter != "label_ids":
            return []

        access_token = credentials.get("access_token")
        if not access_token:
            raise ValueError("access_token is required to fetch labels")

        # List labels for the authenticated user
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self._GMAIL_BASE}/users/me/labels"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            try:
                err = resp.json()
                msg = err.get("error", {}).get("message", str(err))
            except Exception:
                msg = resp.text
            raise ValueError(f"Failed to fetch Gmail labels: {msg}")

        labels = resp.json().get("labels", []) or []
        options: list[ParameterOption] = []
        for lab in labels:
            lid = lab.get("id")
            name = lab.get("name") or lid
            if lid:
                options.append(ParameterOption(value=lid, label=I18nObject(en_US=name)))
        return options
