from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request, Response

from dify_plugin.entities import I18nObject, ParameterOption
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
    """Handle Gmail Pub/Sub push event dispatch.

    Responsibilities:
    - Optionally verify Pub/Sub OIDC JWT
    - Parse Pub/Sub envelope and Gmail notification
    - Fetch Gmail history delta since last checkpoint
    - Split delta into concrete event families and stash batches
    - Return EventDispatch with events and a combined payload for convenience
    """

    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        props = subscription.properties or {}
        # 1) Verify Pub/Sub OIDC if enabled
        self._maybe_verify_pubsub_oidc(request, props, subscription.endpoint)

        # 2) Parse Gmail push notification from Pub/Sub envelope
        notification = self._parse_pubsub_push(request)

        # 3) Build auth headers using runtime OAuth credentials
        access_token = (self.runtime.credentials or {}).get("access_token") if self.runtime else None
        if not access_token:
            raise TriggerDispatchError("Missing access_token for Gmail API")
        headers = {"Authorization": f"Bearer {access_token}"}
        user_id: str = props.get("watch_email") or "me"

        # 4) Prepare storage keys and checkpoint
        sub_key = props.get("subscription_key") or ""
        checkpoint_key = f"gmail:{sub_key}:history_checkpoint"
        keys = {
            "added": f"gmail:{sub_key}:pending:message_added",
            "deleted": f"gmail:{sub_key}:pending:message_deleted",
            "label_added": f"gmail:{sub_key}:pending:label_added",
            "label_removed": f"gmail:{sub_key}:pending:label_removed",
        }

        session = self.runtime.session
        if not session.storage.exist(checkpoint_key):
            # First notification: initialize checkpoint and return 200
            session.storage.set(checkpoint_key, str(notification["historyId"]).encode("utf-8"))
            return EventDispatch(events=[], response=self._ok())

        start_history_id: str = session.storage.get(checkpoint_key).decode("utf-8")

        # 5) Fetch history delta since last checkpoint
        added, deleted, labels_added, labels_removed = self._fetch_history_delta(
            headers=headers, user_id=user_id, start_history_id=start_history_id, fallback_history_id=str(notification["historyId"])
        )

        # Always advance checkpoint to current notification's historyId
        session.storage.set(checkpoint_key, str(notification["historyId"]).encode("utf-8"))

        # 6) Stash batches and build combined payload
        events = []
        def stash(key: str, items: list[dict[str, Any]], event_name: str) -> None:
            if not items:
                return
            payload = json.dumps({"historyId": notification["historyId"], "items": items}).encode("utf-8")
            session.storage.set(key, payload)
            events.append(event_name)

        stash(keys["added"], added, "gmail_message_added")
        stash(keys["deleted"], deleted, "gmail_message_deleted")
        stash(keys["label_added"], labels_added, "gmail_label_added")
        stash(keys["label_removed"], labels_removed, "gmail_label_removed")

        combined_payload = {
            "historyId": str(notification["historyId"]),
            "message_added": added,
            "message_deleted": deleted,
            "label_added": labels_added,
            "label_removed": labels_removed,
        }

        return EventDispatch(events=events, response=self._ok(), payload=combined_payload)

    # ---------------- Helper methods (trigger) -----------------
    def _ok(self) -> Response:
        return Response(response='{"status": "ok"}', status=200, mimetype="application/json")

    def _maybe_verify_pubsub_oidc(self, request: Request, props: Mapping[str, Any], endpoint: str) -> None:
        require_oidc = bool(props.get("require_oidc"))
        if not require_oidc:
            return
        token = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not token:
            raise TriggerValidationError("Missing OIDC bearer token for Pub/Sub push")
        audience = props.get("oidc_audience") or endpoint
        expected_sa = props.get("oidc_service_account_email")
        self._verify_oidc_token(token=token, audience=audience, expected_email=expected_sa)

    def _parse_pubsub_push(self, request: Request) -> dict[str, Any]:
        try:
            envelope: Mapping[str, Any] = request.get_json(force=True)
        except Exception as exc:
            raise TriggerDispatchError(f"Invalid JSON: {exc}") from exc
        if "message" not in envelope:
            raise TriggerDispatchError("Missing Pub/Sub message")
        data_b64: str | None = (envelope.get("message") or {}).get("data")
        if not data_b64:
            raise TriggerDispatchError("Missing Pub/Sub message.data")
        try:
            decoded = base64.b64decode(data_b64).decode("utf-8")
            notification = json.loads(decoded)
        except Exception as exc:
            raise TriggerDispatchError(f"Invalid Pub/Sub data: {exc}") from exc
        if not notification.get("historyId") or not notification.get("emailAddress"):
            raise TriggerDispatchError("Missing historyId or emailAddress in Gmail notification")
        return notification

    def _fetch_history_delta(
        self,
        headers: Mapping[str, str],
        user_id: str,
        start_history_id: str,
        fallback_history_id: str,
    ):
        """Fetch Gmail history delta and return categorized changes.

        If the start_history_id is invalid/out-of-date, reset the pointer and return empty changes.
        """
        added: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []
        labels_added: list[dict[str, Any]] = []
        labels_removed: list[dict[str, Any]] = []

        url = f"{self._GMAIL_BASE}/users/{user_id}/history"
        params: dict[str, Any] = {"startHistoryId": start_history_id}

        while True:
            resp: requests.Response = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                # invalid historyId → caller will advance checkpoint to fallback id and swallow this batch
                return [], [], [], []
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

        return added, deleted, labels_added, labels_removed

    def _verify_oidc_token(self, token: str, audience: str, expected_email: str | None = None) -> None:
        """Verify OIDC token from Pub/Sub push using google-auth if available."""
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token

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
        # Try auto-provision if not provided and system creds exist
        if not topic_name:
            sysc = self.runtime.credentials or {}
            gcp_pid = (sysc.get("gcp_project_id") or "").strip()
            gcp_sa = (sysc.get("gcp_service_account_json") or "").strip()
            if gcp_pid and gcp_sa:
                info = self._ensure_pubsub(
                    project_id=gcp_pid,
                    sa_json=gcp_sa,
                    endpoint=endpoint,
                    topic_id=(sysc.get("gcp_topic_id") or "dify-gmail").strip() or "dify-gmail",
                    require_oidc=bool(parameters.get("require_oidc") or False),
                    audience=(parameters.get("oidc_audience") or endpoint),
                    properties_holder=parameters,
                )
                topic_name = info["topic_path"]
            if not topic_name:
                raise ValueError("topic_name is required (or configure auto Pub/Sub in client params)")
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
        expiration_ms: int | None = int(data.get("expiration"))  # may not be present
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
        # 不向用户暴露托管细节；不写入任何 managed_* 字段

        # internal subscription key for storage scoping
        import uuid as _uuid

        properties["subscription_key"] = _uuid.uuid4().hex

        return Subscription(
            expires_at=expires_at,
            endpoint=endpoint,
            parameters=parameters,
            properties=properties,
        )

    # Minimal auto Pub/Sub helper using google-cloud-pubsub
    def _ensure_pubsub(
        self,
        project_id: str,
        sa_json: str,
        endpoint: str,
        topic_id: str,
        require_oidc: bool,
        audience: str,
        properties_holder: Mapping[str, Any],
    ) -> dict[str, str]:
        import json as _json
        import hashlib as _hashlib
        from google.oauth2 import service_account as _sa
        from google.cloud import pubsub_v1
        from google.api_core.exceptions import AlreadyExists
        from google.iam.v1 import policy_pb2

        info = _json.loads(sa_json) if isinstance(sa_json, str) else sa_json
        creds = _sa.Credentials.from_service_account_info(info)
        sa_email = info.get("client_email")

        publisher = pubsub_v1.PublisherClient(credentials=creds)
        subscriber = pubsub_v1.SubscriberClient(credentials=creds)
        topic_path = publisher.topic_path(project_id, topic_id)
        try:
            publisher.create_topic(name=topic_path)
        except AlreadyExists:
            pass

        # Grant Gmail push service as publisher (idempotent)
        policy = publisher.get_iam_policy(request={"resource": topic_path})
        member = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
        role = "roles/pubsub.publisher"
        if not any(b.role == role and member in b.members for b in policy.bindings):
            policy.bindings.append(policy_pb2.Binding(role=role, members=[member]))
            publisher.set_iam_policy(request={"resource": topic_path, "policy": policy})

        # Create deterministic push subscription per plugin subscription (derived from endpoint)
        sub_id = f"dify-gmail-{_hashlib.sha1(endpoint.encode()).hexdigest()[:16]}"
        sub_path = subscriber.subscription_path(project_id, sub_id)
        push = pubsub_v1.types.PushConfig(push_endpoint=endpoint)
        if require_oidc and sa_email:
            push.oidc_token.service_account_email = sa_email
            push.oidc_token.audience = audience
        try:
            subscriber.create_subscription(name=sub_path, topic=topic_path, push_config=push)
        except AlreadyExists:
            pass

        return {"topic_path": topic_path}

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
            # best-effort cleanup for managed Push subscription (deterministic name)
            sysc = self.runtime.credentials or {}
            proj = (sysc.get("gcp_project_id") or "").strip()
            sa_json = (sysc.get("gcp_service_account_json") or "").strip()
            if proj and sa_json:
                try:
                    import hashlib as _hashlib
                    sub_id = f"dify-gmail-{_hashlib.sha1(subscription.endpoint.encode()).hexdigest()[:16]}"
                    self._delete_managed_subscription(project_id=proj, sa_json=sa_json, subscription_name=sub_id)
                except Exception:
                    pass
            return UnsubscribeResult(success=True, message="Gmail watch stopped")

        try:
            err: dict[str, Any] = resp.json()
        except Exception:
            err = {"message": resp.text}
        return UnsubscribeResult(success=False, message=f"Failed to stop Gmail watch: {err}")

    def _delete_managed_subscription(self, project_id: str, sa_json: str, subscription_name: str) -> None:
        import json as _json
        from google.oauth2 import service_account as _sa
        from google.cloud import pubsub_v1
        from google.api_core.exceptions import NotFound

        info = _json.loads(sa_json) if isinstance(sa_json, str) else sa_json
        creds = _sa.Credentials.from_service_account_info(info)
        subscriber = pubsub_v1.SubscriberClient(credentials=creds)
        sub_path = subscriber.subscription_path(project_id, subscription_name)
        try:
            subscriber.delete_subscription(subscription=sub_path)
        except NotFound:
            pass

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
        expiration_ms: int | None = int(data.get("expiration"))
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
