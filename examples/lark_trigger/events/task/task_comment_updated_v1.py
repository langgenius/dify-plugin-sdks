from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class TaskCommentUpdatedV1Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle task comment updated event.

        This event is triggered when a comment on a task is added or updated.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_task_task_comment_updated_v1,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict: dict[str, Any] = {
            "task_id": event_data.task_id or "",
            "comment_id": event_data.comment_id or "",
            "parent_id": event_data.parent_id or "",
            "obj_type": event_data.obj_type or "",
        }

        return Variables(
            variables=variables_dict,
        )
