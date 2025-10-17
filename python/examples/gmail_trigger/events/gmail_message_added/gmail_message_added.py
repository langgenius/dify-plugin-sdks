from __future__ import annotations

import json
from typing import Any, Mapping

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailMessageAddedEvent(Event):
    _GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        # Read pending batch from storage (set by trigger dispatch)
        sub_key = (self.runtime.subscription.properties or {}).get("subscription_key") or ""
        pending_key = f"gmail:{sub_key}:pending:message_added"

        if not self.runtime.session.storage.exist(pending_key):
            raise EventIgnoreError()

        payload = self.runtime.session.storage.get(pending_key)
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            # Corrupted payload, cleanup and ignore
            self.runtime.session.storage.delete(pending_key)
            raise EventIgnoreError()

        # Cleanup the pending batch to avoid re-processing
        self.runtime.session.storage.delete(pending_key)

        items: list[dict[str, Any]] = data.get("items") or []
        if not items:
            raise EventIgnoreError()

        # Fetch message details for each id
        access_token: str | None = (self.runtime.credentials or {}).get("access_token")
        if not access_token:
            raise ValueError("Missing access token")
        headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
        user_id: str = (self.runtime.subscription.properties or {}).get("watch_email") or "me"

        messages: list[dict[str, Any]] = []
        for it in items:
            mid = it.get("id")
            if not mid:
                continue
            murl = f"{self._GMAIL_BASE}/users/{user_id}/messages/{mid}"
            mparams: dict[str, str] = {"format": "full"}
            mresp: requests.Response = requests.get(murl, headers=headers, params=mparams, timeout=10)
            if mresp.status_code != 200:
                continue
            m = mresp.json() or {}
            headers_list = ((m.get("payload") or {}).get("headers") or [])
            headers_map = {h.get("name"): h.get("value") for h in headers_list if h.get("name")}

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

        if not messages:
            raise EventIgnoreError()

        return Variables(
            variables={
                "history_id": str(data.get("historyId")),
                "messages": messages,
            }
        )
