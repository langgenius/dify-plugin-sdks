from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class FileChangesEvent(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        return Variables(
            variables={
                "changes": payload.get("changes", []),
                "accounts": payload.get("accounts", []),
                "cursor_before": payload.get("cursor_before", ""),
                "cursor_after": payload.get("cursor_after", ""),
                "received_at": payload.get("received_at", 0),
            }
        )
