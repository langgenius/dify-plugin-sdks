from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class ChatMemberBotDeletedV1Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle the event when a bot is removed from a chat group.

        This event is triggered when a bot is removed from a group chat.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_im_chat_member_bot_deleted_v1,
        ).event
        if event_data is None:
            msg = "event_data is None"
            raise ValueError(msg)

        # Build variables dictionary
        variables_dict: dict[str, Any] = {
            "chat_id": event_data.chat_id or "",
            "name": event_data.name or "",
            "is_external": str(event_data.external)
            if event_data.external is not None
            else "false",
            "operator_tenant_key": event_data.operator_tenant_key or "",
        }

        # Add operator information
        if event_data.operator_id:
            variables_dict["operator_user_id"] = event_data.operator_id.user_id or ""
            variables_dict["operator_open_id"] = event_data.operator_id.open_id or ""
            variables_dict["operator_union_id"] = event_data.operator_id.union_id or ""
        else:
            variables_dict["operator_user_id"] = ""
            variables_dict["operator_open_id"] = ""
            variables_dict["operator_union_id"] = ""

        # Add i18n names if available
        if event_data.i18n_names:
            variables_dict["i18n_names"] = {
                "zh_cn": event_data.i18n_names.zh_cn or "",
                "en_us": event_data.i18n_names.en_us or "",
                "ja_jp": event_data.i18n_names.ja_jp or "",
            }
        else:
            variables_dict["i18n_names"] = {}

        return Variables(
            variables=variables_dict,
        )
