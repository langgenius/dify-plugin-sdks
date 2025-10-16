from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailNewEmailEvent(Event):
    """Transform Gmail Pub/Sub notifications into workflow variables."""

    _HISTORY_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/history"
    _MESSAGE_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        payload: Mapping[str, Any] = self._get_payload(request)
        attributes: Mapping[str, Any] = self._get_attributes(request)

        history_id = str(payload.get("historyId") or "")
        email_address = payload.get("emailAddress")
        if not history_id:
            raise EventIgnoreError("Notification does not include historyId")

        credentials = self.runtime.credentials or {}
        access_token = credentials.get("access_token")
        if not access_token:
            raise ValueError("Missing Gmail OAuth access token in runtime credentials")

        history_types = self._normalize_history_types(parameters.get("history_types"))
        max_messages = self._safe_int(parameters.get("max_messages"), default=20, minimum=1, maximum=500)
        include_payload = bool(parameters.get("include_message_payload", False))
        message_format = (parameters.get("message_format") or "metadata").lower()
        metadata_headers = self._normalize_headers(parameters.get("metadata_headers"))

        start_history_id = self._resolve_start_history_id(history_id)
        history_changes = self._fetch_history(
            access_token=access_token,
            start_history_id=start_history_id,
            history_types=history_types,
            max_results=max_messages,
        )

        messages, payloads = self._collect_messages(
            history_changes=history_changes,
            include_payload=include_payload,
            access_token=access_token,
            message_format=message_format,
            metadata_headers=metadata_headers,
            max_messages=max_messages,
        )

        self._persist_latest_history_id(history_id)

        variables = {
            "email_address": email_address,
            "history_id": history_id,
            "start_history_id": start_history_id,
            "message_ids": [message["id"] for message in messages],
            "messages": payloads or messages,
            "raw_payload": payload,
            "attributes": dict(attributes),
        }

        return Variables(variables=variables)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_payload(self, request: Request) -> Mapping[str, Any]:
        payload = request.environ.get("gmail.trigger.payload")
        if isinstance(payload, Mapping):
            return payload

        envelope = request.get_json(silent=True) or {}
        message = envelope.get("message") or {}
        data = message.get("data")
        if not data:
            raise EventIgnoreError("Missing data payload in Pub/Sub message")
        from base64 import b64decode
        import json as _json

        decoded = b64decode(data).decode("utf-8")
        parsed = _json.loads(decoded)
        if not isinstance(parsed, Mapping):
            raise ValueError("Decoded Pub/Sub payload is not a JSON object")
        return parsed

    def _get_attributes(self, request: Request) -> Mapping[str, Any]:
        attributes = request.environ.get("gmail.trigger.attributes")
        if isinstance(attributes, Mapping):
            return attributes

        envelope = request.get_json(silent=True) or {}
        message = envelope.get("message") or {}
        raw_attributes = message.get("attributes") or {}
        if not isinstance(raw_attributes, Mapping):
            return {}
        return raw_attributes

    def _resolve_start_history_id(self, latest_history_id: str) -> str:
        storage = getattr(self.runtime.session, "storage", None)
        if storage:
            storage_key = self._storage_key()
            try:
                saved = storage.get(storage_key)
                if saved:
                    return saved.decode("utf-8")
            except Exception:
                pass

        return str(
            self.runtime.subscription.properties.get("history_id")
            or self.runtime.subscription.properties.get("initial_history_id")
            or latest_history_id
        )

    def _persist_latest_history_id(self, history_id: str) -> None:
        storage = getattr(self.runtime.session, "storage", None)
        if not storage:
            return
        try:
            storage.set(self._storage_key(), history_id.encode("utf-8"))
        except Exception:
            # Persist failure should not block the workflow
            pass

    def _storage_key(self) -> str:
        endpoint = self.runtime.subscription.endpoint
        mailbox = self.runtime.subscription.properties.get("email_address") or "unknown"
        return f"gmail-trigger:last-history:{mailbox}:{endpoint}"

    def _fetch_history(
        self,
        access_token: str,
        start_history_id: str,
        history_types: list[str],
        max_results: int,
    ) -> list[Mapping[str, Any]]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params: dict[str, Any] = {"startHistoryId": start_history_id, "maxResults": max_results}
        if history_types:
            params["historyTypes"] = history_types

        try:
            response = requests.get(self._HISTORY_ENDPOINT, headers=headers, params=params, timeout=10)
        except requests.RequestException as exc:
            raise ValueError(f"Failed to query Gmail history: {exc}") from exc

        if response.status_code == 404:
            # History ID is stale, reset baseline to the latest notification
            return []

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise ValueError(f"Gmail history API error: {payload}")

        history_entries = payload.get("history") or []
        if not isinstance(history_entries, Sequence):
            return []

        return [entry for entry in history_entries if isinstance(entry, Mapping)]

    def _collect_messages(
        self,
        history_changes: Sequence[Mapping[str, Any]],
        include_payload: bool,
        access_token: str,
        message_format: str,
        metadata_headers: list[str],
        max_messages: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        messages: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []

        for change in history_changes:
            if len(messages) >= max_messages:
                break

            messages += self._extract_change_messages(change, "messagesAdded", "added")
            if len(messages) >= max_messages:
                break
            messages += self._extract_change_messages(change, "messagesDeleted", "deleted")
            if len(messages) >= max_messages:
                break

        messages = messages[:max_messages]

        if include_payload and messages:
            for message in messages:
                if len(payloads) >= max_messages:
                    break
                message_id = message.get("id")
                if not message_id:
                    continue
                payload = self._fetch_message_payload(
                    access_token=access_token,
                    message_id=message_id,
                    message_format=message_format,
                    metadata_headers=metadata_headers,
                )
                if payload is not None:
                    payload_with_context = {
                        "id": message_id,
                        "threadId": message.get("threadId"),
                        "change_type": message.get("change_type"),
                        "message": payload,
                    }
                    payloads.append(payload_with_context)

        return messages, payloads

    @staticmethod
    def _extract_change_messages(change: Mapping[str, Any], key: str, change_type: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        items = change.get(key) or []
        if not isinstance(items, Sequence):
            return results

        for item in items:
            if not isinstance(item, Mapping):
                continue
            message = item.get("message") or {}
            if not isinstance(message, Mapping):
                continue
            message_id = message.get("id")
            if not message_id:
                continue
            results.append(
                {
                    "id": message_id,
                    "threadId": message.get("threadId"),
                    "change_type": change_type,
                }
            )
        return results

    def _fetch_message_payload(
        self,
        access_token: str,
        message_id: str,
        message_format: str,
        metadata_headers: list[str],
    ) -> dict[str, Any] | None:
        headers = {"Authorization": f"Bearer {access_token}"}
        params: dict[str, Any] = {"format": message_format}
        if metadata_headers and message_format == "metadata":
            params["metadataHeaders"] = metadata_headers

        try:
            response = requests.get(
                self._MESSAGE_ENDPOINT.format(message_id=message_id),
                headers=headers,
                params=params,
                timeout=10,
            )
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        payload = response.json() if response.content else {}
        if not isinstance(payload, Mapping):
            return None
        return dict(payload)

    @staticmethod
    def _normalize_history_types(raw: Any) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, Sequence):
            return [str(item) for item in raw if str(item)]
        return []

    @staticmethod
    def _normalize_headers(raw: Any) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [header.strip() for header in raw.split(",") if header.strip()]
        if isinstance(raw, Sequence):
            headers: list[str] = []
            for item in raw:
                if isinstance(item, str) and item.strip():
                    headers.append(item.strip())
            return headers
        return []

    @staticmethod
    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, int_value))
