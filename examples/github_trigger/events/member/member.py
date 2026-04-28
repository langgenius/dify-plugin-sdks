from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class MemberUnifiedEvent(Event):
    """Unified Member event (added/edited/removed)."""

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

        member = payload.get("member")
        if not isinstance(member, Mapping):
            msg = "No member in payload"
            raise ValueError(msg)

        filter_login = parameters.get("member")
        if filter_login:
            users = {v.strip() for v in str(filter_login).split(",") if v.strip()}
            if users and (member.get("login") or "") not in users:
                raise EventIgnoreError

        return Variables(variables={**payload})
