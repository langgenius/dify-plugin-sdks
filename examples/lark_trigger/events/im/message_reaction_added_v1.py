from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class MessageReactionAddedV1Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle the event when someone reacts to a message.

        This event is triggered when a user adds an emoji reaction to a message.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_im_message_reaction_created_v1,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict = {
            "message_id": event_data.message_id or "",
            "operator_type": event_data.operator_type or "",
            "action_time": event_data.action_time or "",
            "app_id": event_data.app_id or "",
        }

        # Add reaction emoji information
        if event_data.reaction_type:
            variables_dict["emoji_type"] = event_data.reaction_type.emoji_type or ""

        # Add user information
        if event_data.user_id:
            variables_dict["reactor_user_id"] = event_data.user_id.user_id or ""
            variables_dict["reactor_open_id"] = event_data.user_id.open_id or ""
            variables_dict["reactor_union_id"] = event_data.user_id.union_id or ""

        return Variables(
            variables=variables_dict,
        )
