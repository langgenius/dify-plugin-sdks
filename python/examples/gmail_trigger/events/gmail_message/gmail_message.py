from __future__ import annotations

import base64
import json
from typing import Any, Mapping

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailMessageEvent(Event):
    """Unified Gmail message event using history delta.

    Behavior:
    - First notification: record historyId and return no messages (avoid backfill flood)
    - Subsequent notifications: fetch history since last stored historyId, collect new message ids, fetch details
    - Apply filters (from/to/subject/has_attachments)
    - Return variables with messages array
    """

    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        envelope: Mapping[str, Any] = request.get_json()
        if not isinstance(envelope, Mapping) or "message" not in envelope:
            raise ValueError("Invalid Pub/Sub push envelope: missing message")

        message: Mapping[str, Any] = envelope.get("message") or {}
        data_b64: str | None = message.get("data")
        if not data_b64:
            raise ValueError("Missing Pub/Sub message.data")

        try:
            decoded: str = base64.b64decode(data_b64).decode("utf-8")
            notification: dict[str, Any] = json.loads(decoded)
        except Exception as exc:
            raise ValueError(f"Invalid Pub/Sub data: {exc}") from exc

        email_address = notification.get("emailAddress")
        history_id = str(notification.get("historyId")) if notification.get("historyId") is not None else None
        if not email_address or not history_id:
            raise ValueError("Missing emailAddress or historyId in notification")

        # Credentials from runtime (OAuth)
        if not self.runtime or not self.runtime.credentials:
            raise ValueError("Missing runtime credentials for Gmail API")
        access_token: str | None = self.runtime.credentials.get("access_token")
        if not access_token:
            raise ValueError("Missing access_token for Gmail API")

        # subscription-scoped storage key
        sub_key: str = (self.runtime.subscription.properties or {}).get("subscription_key") or ""
        store_key: str = f"gmail:{sub_key}:history_id"

        session = self.runtime.session

        # First-time initialization: store current history id and return empty messages
        if not session.storage.exist(store_key):
            session.storage.set(store_key, history_id.encode("utf-8"))
            return Variables(
                variables={
                    "email_address": email_address,
                    "history_id": history_id,
                    "messages": [],
                }
            )

        last_history_id: str = session.storage.get(store_key).decode("utf-8")

        # Fetch history delta
        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
        user_id: str = (self.runtime.subscription.properties or {}).get("watch_email") or "me"
        history_url: str = f"{self._GMAIL_BASE}/users/{user_id}/history"
        params: dict[str, Any] = {
            "startHistoryId": last_history_id,
            "historyTypes": "messageAdded",
            # Do not include 'labelId' filters here; watch already scoped at server side if configured
        }

        message_ids: set[str] = set()

        try:
            while True:
                resp: requests.Response = requests.get(history_url, headers=headers, params=params, timeout=10)
                if resp.status_code != 200:
                    # If historyId is invalid/out of date, reset to current and ignore
                    try:
                        err: dict[str, Any] = resp.json()
                        reason = (err.get("error", {}).get("errors", [{}])[0].get("reason")) or err.get(
                            "error", {}
                        ).get("status")
                    except Exception:
                        reason = ""
                    if reason and "history" in reason.lower():
                        # reset position and swallow this batch
                        session.storage.set(store_key, history_id.encode("utf-8"))
                        return Variables(
                            variables={"email_address": email_address, "history_id": history_id, "messages": []}
                        )
                    raise ValueError(f"Gmail history.list failed: {resp.text}")

                data: dict[str, Any] = resp.json() or {}
                for h in data.get("history", []) or []:
                    for added in h.get("messagesAdded", []) or []:
                        msg = added.get("message") or {}
                        if msg.get("id"):
                            message_ids.add(msg["id"])

                page_token = data.get("nextPageToken")
                if not page_token:
                    break
                params["pageToken"] = page_token
        finally:
            # Always move the pointer forward to the latest notification's history id
            session.storage.set(store_key, history_id.encode("utf-8"))

        # Fetch message details
        messages: list[dict[str, Any]] = []
        if message_ids:
            for mid in message_ids:
                murl = f"{self._GMAIL_BASE}/users/{user_id}/messages/{mid}"
                mparams: dict[str, str] = {
                    "format": "full",  # need payload.parts for attachments detection
                }
                mresp: requests.Response = requests.get(murl, headers=headers, params=mparams, timeout=10)
                if mresp.status_code != 200:
                    continue
                m: dict[str, Any] = mresp.json() or {}
                headers_list: list[dict[str, Any]] = (m.get("payload") or {}).get("headers") or []
                headers_map = {h.get("name"): h.get("value") for h in headers_list if h.get("name")}

                # attachments detection: any part with filename
                has_attachments = False
                attachments_meta: list[dict[str, Any]] = []

                def _walk_parts(part: Mapping[str, Any] | None):
                    nonlocal has_attachments, attachments_meta
                    if not part:
                        return
                    filename = part.get("filename")
                    if filename:
                        has_attachments = True
                        attachments_meta.append(
                            {
                                "filename": filename,
                                "mimeType": part.get("mimeType"),
                                "size": ((part.get("body") or {}).get("size")),
                            }
                        )
                    for p in (part.get("parts") or []) or []:
                        _walk_parts(p)

                _walk_parts((m.get("payload") or {}))

                messages.append(
                    {
                        "id": m.get("id"),
                        "threadId": m.get("threadId"),
                        "internalDate": m.get("internalDate"),
                        "snippet": m.get("snippet"),
                        "sizeEstimate": m.get("sizeEstimate"),
                        "labelIds": m.get("labelIds") or [],
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

        # Apply filters
        def _contains_any(val: str | None, cond: str | None) -> bool:
            if not cond:
                return True
            if not val:
                return False
            tokens = [t.strip() for t in cond.split(",") if t.strip()]
            return any(t.lower() in val.lower() for t in tokens)

        from_cond = parameters.get("from_contains")
        to_cond = parameters.get("to_contains")
        subject_cond = parameters.get("subject_contains")
        has_attachments_cond = parameters.get("has_attachments")

        filtered: list[dict[str, Any]] = []
        for m in messages:
            if not _contains_any(m.get("headers", {}).get("From"), from_cond):
                continue
            if not _contains_any(m.get("headers", {}).get("To"), to_cond):
                continue
            if not _contains_any(m.get("headers", {}).get("Subject"), subject_cond):
                continue
            if has_attachments_cond is True and not m.get("has_attachments"):
                continue
            if has_attachments_cond is False and m.get("has_attachments"):
                continue
            filtered.append(m)

        if not filtered:
            # If no messages match, ignore event to avoid triggering downstream flows
            raise EventIgnoreError()

        return Variables(
            variables={
                "email_address": email_address,
                "history_id": history_id,
                "messages": filtered,
            }
        )
