from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailMessageEvent(Event):
    """Unified Gmail message event (added and deleted messages)."""

    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        history_id = payload.get("historyId")
        added_items = self._normalize_items(payload.get("message_added") or payload.get("items"))
        deleted_items = self._normalize_items(payload.get("message_deleted"))

        if not added_items and not deleted_items:
            raise EventIgnoreError()

        access_token: str | None = (self.runtime.credentials or {}).get("access_token") if self.runtime else None
        if not access_token:
            raise ValueError("Missing access token")
        headers = {"Authorization": f"Bearer {access_token}"}

        selected_labels: set[str] = self._normalize_string_set(
            (self.runtime.subscription.properties or {}).get("label_ids") if self.runtime else None
        )

        from_terms = self._parse_terms(parameters.get("from_contains"))
        to_terms = self._parse_terms(parameters.get("to_contains"))
        subject_terms = self._parse_terms(parameters.get("subject_contains"))
        has_attachments_condition = self._normalize_bool(parameters.get("has_attachments"))

        messages: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for item in added_items:
            message_id = item.get("id")
            if not message_id or (message_id, "added") in seen:
                continue

            message = self._fetch_message(message_id=str(message_id), headers=headers)
            if not message:
                continue

            label_ids: list[str] = [str(lid) for lid in (message.get("labelIds") or []) if lid]
            if selected_labels and not selected_labels.intersection(label_ids):
                continue

            headers_map = self._extract_headers(message)
            has_attachments, attachments_meta = self._extract_attachments(
                message.get("payload") or {}, message.get("id")
            )

            if not self._matches_terms(headers_map.get("From"), from_terms):
                continue
            if not self._matches_terms(headers_map.get("To"), to_terms):
                continue
            if not self._matches_terms(headers_map.get("Subject"), subject_terms):
                continue
            if has_attachments_condition is True and not has_attachments:
                continue
            if has_attachments_condition is False and has_attachments:
                continue

            seen.add((message_id, "added"))
            messages.append(
                {
                    "id": message.get("id"),
                    "threadId": message.get("threadId"),
                    "change_type": "added",
                    "internalDate": message.get("internalDate"),
                    "snippet": message.get("snippet"),
                    "sizeEstimate": message.get("sizeEstimate"),
                    "labelIds": label_ids,
                    "headers": {
                        "From": headers_map.get("From"),
                        "To": headers_map.get("To"),
                        "Subject": headers_map.get("Subject"),
                        "Date": headers_map.get("Date"),
                        "Message-Id": headers_map.get("Message-Id"),
                    },
                    "has_attachments": has_attachments,
                    "attachments": attachments_meta,
                }
            )

        for item in deleted_items:
            message_id = item.get("id")
            if not message_id or (message_id, "deleted") in seen:
                continue
            seen.add((message_id, "deleted"))
            messages.append(
                {
                    "id": message_id,
                    "threadId": item.get("threadId"),
                    "change_type": "deleted",
                }
            )

        if not messages:
            raise EventIgnoreError()

        email_address = self._extract_email_address(request, payload)

        return Variables(
            variables={
                "email_address": email_address,
                "history_id": str(history_id or ""),
                "messages": messages,
            }
        )

    def _normalize_items(self, raw: Any) -> list[Mapping[str, Any]]:
        if not isinstance(raw, list):
            return []
        return [it for it in raw if isinstance(it, Mapping)]

    def _normalize_string_set(self, raw: Any) -> set[str]:
        if not raw:
            return set()
        if isinstance(raw, str):
            return {raw}
        if isinstance(raw, (list, tuple, set)):
            return {str(item) for item in raw if isinstance(item, (str, int))}
        return set()

    def _parse_terms(self, raw: Any) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            base = raw
        elif isinstance(raw, (list, tuple)):
            base = ",".join(str(item) for item in raw if item)
        else:
            base = str(raw)
        return [part.strip().lower() for part in base.split(",") if part and part.strip()]

    def _matches_terms(self, value: Any, terms: list[str]) -> bool:
        if not terms:
            return True
        if value is None:
            return False
        text = str(value).lower()
        return any(term in text for term in terms)

    def _normalize_bool(self, raw: Any) -> bool | None:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        return None

    def _fetch_message(self, message_id: str, headers: Mapping[str, str]) -> dict[str, Any] | None:
        url = f"{self._GMAIL_BASE}/users/me/messages/{message_id}"
        params = {"format": "full"}
        try:
            response: requests.Response = requests.get(url, headers=headers, params=params, timeout=10)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        try:
            return response.json() or {}
        except ValueError:
            return None

    def _extract_headers(self, message: Mapping[str, Any]) -> dict[str, str]:
        headers_list = (message.get("payload") or {}).get("headers") or []
        header_map: dict[str, str] = {}
        for header in headers_list:
            name = header.get("name")
            value = header.get("value")
            if name and value is not None and name not in header_map:
                header_map[name] = value
        return header_map

    def _extract_attachments(
        self, payload: Mapping[str, Any], message_id: Any
    ) -> tuple[bool, list[dict[str, Any]]]:
        has_attachments = False
        attachments: list[dict[str, Any]] = []
        msg_id: str | None = str(message_id) if message_id else None

        def _walk(part: Mapping[str, Any] | None) -> None:
            nonlocal has_attachments, attachments
            if not part:
                return
            filename = part.get("filename")
            if filename:
                has_attachments = True
                body = part.get("body")
                attachment_id: str | None = None
                size: Any = None
                if isinstance(body, Mapping):
                    raw_attachment_id = body.get("attachmentId")
                    if isinstance(raw_attachment_id, str):
                        attachment_id = raw_attachment_id
                    size = body.get("size")
                download_url: str | None = (
                    f"{self._GMAIL_BASE}/users/me/messages/{msg_id}/attachments/{attachment_id}"
                    if attachment_id and msg_id
                    else None
                )
                attachments.append(
                    {
                        "filename": filename,
                        "mimeType": part.get("mimeType"),
                        "size": size,
                        "attachmentId": attachment_id,
                        "download_url": download_url,
                    }
                )
            for child in (part.get("parts") or []) or []:
                if isinstance(child, Mapping):
                    _walk(child)

        _walk(payload or {})
        return has_attachments, attachments

    def _extract_email_address(self, request: Request, payload: Mapping[str, Any]) -> str:
        if isinstance(payload.get("emailAddress"), str):
            return str(payload["emailAddress"])
        try:
            envelope = request.get_json(force=False, silent=True) or {}
        except Exception:
            envelope = {}
        message = envelope.get("message") or {}
        data_b64 = message.get("data")
        if not data_b64:
            return self._fallback_email()
        try:
            decoded = base64.b64decode(data_b64).decode("utf-8")
            notification = json.loads(decoded)
        except Exception:
            return self._fallback_email()
        email = notification.get("emailAddress")
        if not email:
            return self._fallback_email()
        return str(email)

    def _fallback_email(self) -> str:
        return str((self.runtime.subscription.properties or {}).get("watch_email") or "") if self.runtime else ""
