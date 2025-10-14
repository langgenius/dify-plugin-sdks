from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import (
    dispatch_single_event,
    serialize_user_identity,
    serialize_user_list,
)


class CalendarAclDeletedV4Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """Handle calendar ACL deletion events."""

        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder, callback: builder.register_p2_calendar_calendar_acl_deleted_v4(
                callback
            ),
        )
        scope = event_data.scope
        scope_user_source = scope.user_id if scope and scope.user_id else None
        scope_user = serialize_user_identity(scope_user_source)

        variables_dict: dict[str, Any] = {
            "acl_id": event_data.acl_id or "",
            "role": event_data.role or "",
            "scope_type": scope.type if scope and scope.type else "",
            "scope_user_id": scope_user["user_id"],
            "scope_open_id": scope_user["open_id"],
            "scope_union_id": scope_user["union_id"],
            "affected_users": serialize_user_list(event_data.user_id_list or []),
        }

        return Variables(
            variables=variables_dict,
        )
