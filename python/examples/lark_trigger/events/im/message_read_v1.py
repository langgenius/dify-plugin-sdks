from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.im.v1 import P2ImMessageMessageReadV1

import lark_oapi as lark


class MessageReadV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle the event when messages are marked as read.
        
        This event is triggered when a user reads one or more messages.
        """
        event: dict[str, P2ImMessageMessageReadV1] = {}

        def _handle_message_read_v1(on_event: P2ImMessageMessageReadV1) -> None:
            """
            Handle the message read event.
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
            .register_p2_im_message_message_read_v1(
                _handle_message_read_v1,
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
        variables_dict = {}
        
        # Add reader information
        if event_data.reader:
            variables_dict["reader_id_type"] = event_data.reader.reader_id_type if event_data.reader.reader_id_type else ""
            variables_dict["reader_id"] = event_data.reader.reader_id if event_data.reader.reader_id else ""
            variables_dict["read_time"] = event_data.reader.read_time if event_data.reader.read_time else ""
            variables_dict["tenant_key"] = event_data.reader.tenant_key if event_data.reader.tenant_key else ""
        
        # Add message IDs that were read
        if event_data.message_id_list:
            import json
            variables_dict["message_ids_read"] = json.dumps(event_data.message_id_list, ensure_ascii=False)
            variables_dict["message_count"] = str(len(event_data.message_id_list))
        else:
            variables_dict["message_ids_read"] = "[]"
            variables_dict["message_count"] = "0"

        return Variables(
            variables=variables_dict,
        )