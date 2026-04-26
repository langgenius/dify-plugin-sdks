from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class ProjectColumnUnifiedEvent(Event):
    """Unified Project Column event (created/edited/deleted/moved)."""

    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        payload = request.get_json()
        if not payload:
            msg = "No payload received"
            raise ValueError(msg)

        allowed_actions = parameters.get("actions") or []
        action = payload.get("action")
        if allowed_actions and action not in allowed_actions:
            raise EventIgnoreError

        column = payload.get("project_column")
        if not isinstance(column, Mapping):
            msg = "No project_column in payload"
            raise ValueError(msg)

        name_filter = parameters.get("column_name")
        if name_filter:
            names = {v.strip() for v in str(name_filter).split(",") if v.strip()}
            if names and (column.get("name") or "") not in names:
                raise EventIgnoreError

        return Variables(variables={**payload})
