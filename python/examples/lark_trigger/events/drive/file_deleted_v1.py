from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import (
    dispatch_single_event,
    dumps_json,
    serialize_user_identity,
    serialize_user_list,
)


class DriveFileDeletedV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """Handle drive file deletion events."""

        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder, callback: builder.register_p2_drive_file_deleted_v1(callback),
        )
        operator = serialize_user_identity(event_data.operator_id)
        subscribers = serialize_user_list(event_data.subscriber_id_list or [])

        variables_dict: dict[str, Any] = {
            "file_token": event_data.file_token or "",
            "file_type": event_data.file_type or "",
            "operator_user_id": operator["user_id"],
            "operator_open_id": operator["open_id"],
            "operator_union_id": operator["union_id"],
            "subscriber_users": dumps_json(subscribers),
            "subscriber_count": len(subscribers),
        }

        return Variables(
            variables=variables_dict,
        )
