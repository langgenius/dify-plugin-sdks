from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from examples.lark_trigger.events._shared import dispatch_single_event


class ApprovalUpdatedV4Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle approval process updates.

        This event is triggered when an approval request status changes.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_approval_approval_updated_v4,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        approval_data = event_data.object
        if approval_data is None:
            msg = "approval_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict = {
            "approval_code": approval_data.approval_code or "",
            "approval_id": approval_data.approval_id or "",
            "timestamp": approval_data.timestamp or "",
            "version_id": approval_data.version_id or "",
            "form_definition_id": approval_data.form_definition_id or "",
            "widget_group_type": approval_data.widget_group_type
            if approval_data.widget_group_type is not None
            else 0,
            "process_obj": approval_data.process_obj or "",
            "extra": approval_data.extra or "",
        }

        return Variables(
            variables=variables_dict,
        )
