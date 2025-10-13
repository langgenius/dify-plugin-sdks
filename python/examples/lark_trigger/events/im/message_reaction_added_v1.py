from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.im.v1 import P2ImMessageReactionCreatedV1

import lark_oapi as lark


class MessageReactionAddedV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle the event when someone reacts to a message.
        
        This event is triggered when a user adds an emoji reaction to a message.
        """
        event: dict[str, P2ImMessageReactionCreatedV1] = {}

        def _handle_message_reaction_created_v1(on_event: P2ImMessageReactionCreatedV1) -> None:
            """
            Handle the message reaction created event.
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
            .register_p2_im_message_reaction_created_v1(
                _handle_message_reaction_created_v1,
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
            "message_id": event_data.message_id if event_data.message_id else "",
            "operator_type": event_data.operator_type if event_data.operator_type else "",
            "action_time": event_data.action_time if event_data.action_time else "",
            "app_id": event_data.app_id if event_data.app_id else "",
        }
        
        # Add reaction emoji information
        if event_data.reaction_type:
            variables_dict["emoji_type"] = event_data.reaction_type.emoji_type if event_data.reaction_type.emoji_type else ""
        
        # Add user information
        if event_data.user_id:
            variables_dict["reactor_user_id"] = event_data.user_id.user_id if event_data.user_id.user_id else ""
            variables_dict["reactor_open_id"] = event_data.user_id.open_id if event_data.user_id.open_id else ""
            variables_dict["reactor_union_id"] = event_data.user_id.union_id if event_data.user_id.union_id else ""

        return Variables(
            variables=variables_dict,
        )