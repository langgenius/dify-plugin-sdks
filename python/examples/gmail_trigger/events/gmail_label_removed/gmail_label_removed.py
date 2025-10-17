from __future__ import annotations

import json
from typing import Any, Mapping

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GmailLabelRemovedEvent(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        sub_key = (self.runtime.subscription.properties or {}).get("subscription_key") or ""
        pending_key = f"gmail:{sub_key}:pending:label_removed"

        if not self.runtime.session.storage.exist(pending_key):
            raise EventIgnoreError()

        payload: bytes = self.runtime.session.storage.get(pending_key)
        try:
            data: dict[str, Any] = json.loads(payload.decode("utf-8"))
        except Exception:
            self.runtime.session.storage.delete(pending_key)
            raise EventIgnoreError()

        self.runtime.session.storage.delete(pending_key)

        items: list[dict[str, Any]] = data.get("items") or []
        if not items:
            raise EventIgnoreError()

        return Variables(variables={"history_id": str(data.get("historyId")), "changes": items})
