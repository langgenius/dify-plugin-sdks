from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class FileChangesEvent(Event):
    def _on_event(self, payload: Mapping[str, Any]) -> Variables:  # type: ignore[override]
        return Variables(payload)

