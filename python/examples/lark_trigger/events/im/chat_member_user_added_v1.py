from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.im.v1 import P2ImChatMemberUserAddedV1

import lark_oapi as lark


class ChatMemberUserAddedV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle the event when new members join a chat group.
        
        This event is triggered when one or more users are added to a chat group.
        """
        event: dict[str, P2ImChatMemberUserAddedV1] = {}

        def _handle_chat_member_user_added_v1(on_event: P2ImChatMemberUserAddedV1) -> None:
            """
            Handle the chat member user added event.
            """
            event["on_event"] = on_event

        encrypt_key = self.runtime.subscription.properties.get("lark_encrypt_key", "")
        verification_token = self.runtime.subscription.properties.get("lark_verification_token", "")

        if not encrypt_key or not verification_token:
            raise ValueError("encrypt_key or verification_token is not set")

        handler = (
            lark.EventDispatcherHandler.builder(
                encrypt_key,
                verification_token,
            )
            .register_p2_im_chat_member_user_added_v1(
                _handle_chat_member_user_added_v1,
            )
            .build()
        )

        raw_request = RawRequest()
        raw_request.uri = request.url
        raw_request.headers = request.headers
        raw_request.body = request.get_data()

        handler.do(raw_request)

        if event["on_event"] is None:
            raise ValueError("event is None")

        if event["on_event"].event is None:
            raise ValueError("event.event is None")

        event_data = event["on_event"].event
        
        # Build variables dictionary
        variables_dict = {
            "chat_id": event_data.chat_id if event_data.chat_id else "",
            "chat_name": event_data.name if event_data.name else "",
            "is_external": str(event_data.external) if event_data.external is not None else "false",
            "operator_tenant_key": event_data.operator_tenant_key if event_data.operator_tenant_key else "",
        }
        
        # Add operator information
        if event_data.operator_id:
            variables_dict["operator_user_id"] = event_data.operator_id.user_id if event_data.operator_id.user_id else ""
            variables_dict["operator_open_id"] = event_data.operator_id.open_id if event_data.operator_id.open_id else ""
            variables_dict["operator_union_id"] = event_data.operator_id.union_id if event_data.operator_id.union_id else ""
        
        # Add new members information
        if event_data.users:
            members_list = []
            for idx, user in enumerate(event_data.users):
                if user:
                    member_info = {
                        "name": user.name if user.name else "",
                        "tenant_key": user.tenant_key if user.tenant_key else "",
                    }
                    if user.user_id:
                        member_info["user_id"] = user.user_id.user_id if user.user_id.user_id else ""
                        member_info["open_id"] = user.user_id.open_id if user.user_id.open_id else ""
                        member_info["union_id"] = user.user_id.union_id if user.user_id.union_id else ""
                    members_list.append(member_info)
            
            # Convert list to JSON string for compatibility
            import json
            variables_dict["new_members"] = json.dumps(members_list, ensure_ascii=False)
            variables_dict["new_members_count"] = str(len(members_list))

        return Variables(
            variables=variables_dict,
        )