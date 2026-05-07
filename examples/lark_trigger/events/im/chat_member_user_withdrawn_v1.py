from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class ChatMemberUserWithdrawnV1Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle the event when a user withdraws from a chat group.

        This event is triggered when a user voluntarily withdraws/leaves from
        a chat group.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_im_chat_member_user_withdrawn_v1,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict: dict[str, Any] = {
            "chat_id": event_data.chat_id or "",
            "name": event_data.name or "",
            "operator_tenant_key": event_data.operator_tenant_key or "",
        }

        # Add withdrawn user information
        if event_data.users:
            withdrawn_users = []
            for user in event_data.users:
                if user:
                    user_info = {
                        "name": user.name or "",
                        "tenant_key": user.tenant_key or "",
                    }
                    if user.user_id:
                        user_info["user_id"] = user.user_id.user_id or ""
                        user_info["open_id"] = user.user_id.open_id or ""
                        user_info["union_id"] = user.user_id.union_id or ""
                    withdrawn_users.append(user_info)

            variables_dict["withdrawn_users"] = withdrawn_users
            variables_dict["withdrawn_users_count"] = len(withdrawn_users)
        else:
            variables_dict["withdrawn_users"] = []
            variables_dict["withdrawn_users_count"] = 0

        return Variables(
            variables=variables_dict,
        )
