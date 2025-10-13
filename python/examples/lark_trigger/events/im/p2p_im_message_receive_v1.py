from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

import lark_oapi as lark


class P2PIMMessageReceiveV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle the P2P IM message receive event.

        The event is triggered when the Bot receives an IM message.
        The event will return the message content.
        """
        event: dict[str, P2ImMessageReceiveV1] = {}

        def _handle_p2_im_message_receive_v1(on_event: P2ImMessageReceiveV1) -> None:
            """
            Handle the P2P IM message receive event.
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
            .register_p2_im_message_receive_v1(
                _handle_p2_im_message_receive_v1,
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

        if event["on_event"].event.message is None:
            raise ValueError("event.event.message is None")

        if event["on_event"].event.message.content is None:
            raise ValueError("event.event.message.content is None")

        # Extract message details
        message = event["on_event"].event.message
        sender = event["on_event"].event.sender if event["on_event"].event.sender else None

        # Build variables dictionary with all available message fields
        variables_dict = {
            # Message content
            "content": message.content,
            "message_id": message.message_id if message.message_id else "",
            "message_type": message.message_type if message.message_type else "",
            # Chat information
            "chat_id": message.chat_id if message.chat_id else "",
            "chat_type": message.chat_type if message.chat_type else "",
            # Thread information
            "root_id": message.root_id if message.root_id else "",
            "parent_id": message.parent_id if message.parent_id else "",
            "thread_id": message.thread_id if message.thread_id else "",
            # Timestamps (converted to string for JSON compatibility)
            "create_time": str(message.create_time) if message.create_time else "",
            "update_time": str(message.update_time) if message.update_time else "",
            # User agent
            "user_agent": message.user_agent if message.user_agent else "",
        }

        # Add sender information if available
        if sender:
            variables_dict["sender_type"] = sender.sender_type if sender.sender_type else ""
            variables_dict["tenant_key"] = sender.tenant_key if sender.tenant_key else ""

            # Add sender IDs if available
            if sender.sender_id:
                variables_dict["sender_user_id"] = sender.sender_id.user_id if sender.sender_id.user_id else ""
                variables_dict["sender_open_id"] = sender.sender_id.open_id if sender.sender_id.open_id else ""
                variables_dict["sender_union_id"] = sender.sender_id.union_id if sender.sender_id.union_id else ""

        return Variables(
            variables=variables_dict,
        )
