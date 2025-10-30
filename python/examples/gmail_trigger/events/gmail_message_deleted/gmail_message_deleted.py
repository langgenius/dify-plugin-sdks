from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailMessageDeletedEvent(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        # Prefer payload delivered from Trigger.dispatch_event
        history_id = payload.get("historyId")
        items: list[dict[str, Any]] = []
        raw_items = payload.get("message_deleted") or payload.get("items")
        if isinstance(raw_items, list):
            items = [it for it in raw_items if isinstance(it, Mapping)]  # type: ignore[typeddict-item]

        # Fallback to storage when payload not provided
        if not items:
            sub_key = (self.runtime.subscription.properties or {}).get("subscription_key") or ""
            pending_key = f"gmail:{sub_key}:pending:message_deleted"

            if not self.runtime.session.storage.exist(pending_key):
                raise EventIgnoreError()

            raw_bytes: bytes = self.runtime.session.storage.get(pending_key)
            try:
                data: dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))
            except Exception:
                self.runtime.session.storage.delete(pending_key)
                raise EventIgnoreError()

            # Cleanup pending batch
            self.runtime.session.storage.delete(pending_key)
            history_id = history_id or data.get("historyId")
            items = data.get("items") or []

        if not items:
            raise EventIgnoreError()

        # For deleted messages we cannot retrieve content anymore; output ids only
        return Variables(variables={"history_id": str(history_id or ""), "messages": items})
