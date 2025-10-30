from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

import hashlib as _hashlib
import requests
from werkzeug import Request, Response

from dify_plugin.entities.trigger import EventDispatch, Subscription
from dify_plugin.errors.trigger import (
    TriggerDispatchError,
    TriggerValidationError,
)
from dify_plugin.interfaces.trigger import Trigger


class DropboxTrigger(Trigger):
    """Manual webhook mode for Dropbox.

    Users create their own Dropbox App and set the App's webhook URL to the subscription endpoint.
    This trigger validates signatures and emits a lightweight notification with the account IDs and raw payload.
    """

    _EVENT_NAME = "file_changes"
    _MAX_PAGES = 10

    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        # Dropbox webhook verification challenge (GET)
        if request.method == "GET":
            challenge = request.args.get("challenge")
            if challenge:
                return EventDispatch(
                    events=[],
                    response=Response(response=challenge, mimetype="text/plain", status=200),
                )
            return EventDispatch(events=[], response=self._ok_response())

        # Only POST carries notifications
        if request.method != "POST":
            return EventDispatch(events=[], response=self._ok_response())

        app_secret = str(subscription.properties.get("app_secret") or "")
        if not app_secret:
            raise TriggerDispatchError("Dropbox App Secret missing from subscription properties")

        # Validate signature
        self._validate_signature(request=request, app_secret=app_secret)

        # Parse body (raw JSON)
        try:
            body_text = request.get_data(cache=True, as_text=True)
            payload = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError as exc:
            raise TriggerDispatchError("Invalid JSON payload for Dropbox webhook") from exc

        # Extract notified account IDs (if present)
        notified_accounts: list[str] = payload.get("list_folder", {}).get("accounts")
        # Fetch changes if access_token is configured
        access_token = str(subscription.properties.get("access_token") or "")

        cursor_before = ""
        cursor_after = ""
        changes: list[dict[str, Any]] = []

        if access_token:
            storage_key = self._cursor_storage_key(access_token)
            cursor_before = self._get_cursor(storage_key)

            if not cursor_before:
                # First time: get latest cursor as starting point
                cursor_before = self._get_latest_cursor(access_token)
                # Save the cursor for next time use
                self._set_cursor(storage_key, cursor_before)
                # Next time: fetch changes since cursor_before
                return EventDispatch(events=[], response=self._ok_response(), payload={})

            # Fetch changes since cursor_before
            cursor = cursor_before
            for _ in range(self._MAX_PAGES):
                page, cursor, has_more = self._list_folder_continue(access_token, cursor)
                changes.extend(self._format_entries(page))
                if not has_more:
                    break

            # Save the new cursor for next time
            self._set_cursor(storage_key, cursor)
            cursor_after = cursor

        payload_out = {
            "accounts": notified_accounts,
            "cursor_before": cursor_before,
            "cursor_after": cursor_after,
            "changes": changes,
            "raw": payload,
            "headers": {"x_dropbox_request_id": request.headers.get("X-Dropbox-Request-Id")},
            "received_at": int(time.time()),
        }

        return EventDispatch(events=[self._EVENT_NAME], response=self._ok_response(), payload=payload_out)

    # ----------------------------- Helpers -----------------------------
    @staticmethod
    def _ok_response() -> Response:
        return Response(response=json.dumps({"status": "ok"}), mimetype="application/json", status=200)

    @staticmethod
    def _validate_signature(request: Request, app_secret: str) -> None:
        signature = request.headers.get("X-Dropbox-Signature")
        if not signature:
            raise TriggerValidationError("Missing X-Dropbox-Signature header")
        body = request.get_data(cache=True, as_text=False) or b""
        expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise TriggerValidationError("Invalid Dropbox webhook signature")

    # ----------------------------- Dropbox API helpers -----------------------------
    def _get_latest_cursor(self, access_token: str) -> str:
        """Get the latest cursor without fetching file list."""
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body = {
            "path": "",
            "recursive": True,
            "include_deleted": True,
            "include_non_downloadable_files": True,
        }
        try:
            resp = requests.post(
                "https://api.dropboxapi.com/2/files/list_folder/get_latest_cursor",
                headers=headers,
                json=body,
                timeout=10,
            )
        except Exception as exc:
            raise TriggerDispatchError(f"Failed to get Dropbox cursor: {exc}") from exc
        data = resp.json() if resp.content else {}
        if resp.status_code != 200:
            raise TriggerDispatchError(f"Dropbox get_latest_cursor error: {data}")
        cursor = str(data.get("cursor") or "")
        if not cursor:
            raise TriggerDispatchError("Dropbox cursor missing in response")
        return cursor

    def _list_folder_continue(self, access_token: str, cursor: str) -> tuple[list[Mapping[str, Any]], str, bool]:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body = {"cursor": cursor}
        try:
            resp = requests.post(
                "https://api.dropboxapi.com/2/files/list_folder/continue", headers=headers, json=body, timeout=10
            )
        except Exception as exc:
            raise TriggerDispatchError(f"Failed to fetch Dropbox changes: {exc}") from exc
        data = resp.json() if resp.content else {}
        if resp.status_code != 200:
            raise TriggerDispatchError(f"Dropbox list_folder/continue error: {data}")
        entries = data.get("entries") or []
        has_more = bool(data.get("has_more"))
        new_cursor = str(data.get("cursor") or cursor)
        normalized: list[Mapping[str, Any]] = []
        if isinstance(entries, Sequence):
            for e in entries:
                if isinstance(e, Mapping):
                    normalized.append(e)
        return list(normalized), new_cursor, has_more

    # ----------------------------- Entry formatting and storage -----------------------------
    def _format_entries(self, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for e in entries:
            tag = str(e.get(".tag") or e.get("tag") or "").lower()
            action = "deleted" if tag == "deleted" else "upsert"
            path_lower = str(e.get("path_lower") or "")
            path_display = str(e.get("path_display") or "")
            results.append(
                {
                    "action": action,
                    "tag": tag,
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "path_display": path_display,
                    "path_lower": path_lower,
                    "server_modified": e.get("server_modified"),
                    "client_modified": e.get("client_modified"),
                    "rev": e.get("rev"),
                    "size": e.get("size"),
                    "content_hash": e.get("content_hash"),
                }
            )
        return results

    @staticmethod
    def _token_hash(token: str) -> str:
        return _hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]

    def _cursor_storage_key(self, access_token: str) -> str:
        return f"dropbox:last-cursor:{self._token_hash(access_token)}"

    def _account_id_storage_key(self, access_token: str) -> str:
        return f"dropbox:account-id:{self._token_hash(access_token)}"

    # simple storage wrappers
    def _get_storage(self, key: str) -> str:
        try:
            raw = self.runtime.session.storage.get(key)
            return raw.decode("utf-8") if raw else ""
        except Exception:
            return ""

    def _set_storage(self, key: str, value: str) -> None:
        try:
            self.runtime.session.storage.set(key, value.encode("utf-8"))
        except Exception:
            pass

    def _get_cursor(self, key: str) -> str:
        return self._get_storage(key)

    def _set_cursor(self, key: str, cursor: str) -> None:
        self._set_storage(key, cursor)
