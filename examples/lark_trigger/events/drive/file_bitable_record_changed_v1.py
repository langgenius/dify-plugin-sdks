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


class DriveFileBitableRecordChangedV1Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle bitable record changed event.

        This event is triggered when a record in a bitable (database table) is changed.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_drive_file_bitable_record_changed_v1,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict: dict[str, Any] = {
            "file_token": event_data.file_token or "",
            "file_type": event_data.file_type or "",
            "table_id": event_data.table_id or "",
            "revision": event_data.revision or 0,
            "update_time": event_data.update_time or "",
        }

        # Add operator information
        operator = serialize_user_identity(event_data.operator_id)
        variables_dict.update({
            "operator_user_id": operator["user_id"],
            "operator_open_id": operator["open_id"],
            "operator_union_id": operator["union_id"],
        })

        # Add subscribers
        subscribers = serialize_user_list(event_data.subscriber_id_list or [])
        variables_dict["subscribers"] = subscribers

        # Process action list
        if event_data.action_list:
            actions = []
            for action in event_data.action_list:
                if action:
                    action_info = {
                        "action": action.action or "",
                        "record_id": action.record_id or "",
                        "before_value": action.before_value or "",
                        "after_value": action.after_value or "",
                    }
                    actions.append(action_info)
            variables_dict["actions"] = actions
            variables_dict["action_count"] = len(actions)
        else:
            variables_dict["actions"] = []
            variables_dict["action_count"] = 0

        return Variables(
            variables=variables_dict,
        )
