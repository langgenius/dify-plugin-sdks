from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.approval.v4 import P2ApprovalApprovalUpdatedV4

import lark_oapi as lark


class ApprovalUpdatedV4Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle approval process updates.
        
        This event is triggered when an approval request status changes.
        """
        event: dict[str, P2ApprovalApprovalUpdatedV4] = {}

        def _handle_approval_updated_v4(on_event: P2ApprovalApprovalUpdatedV4) -> None:
            """
            Handle the approval updated event.
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
            .register_p2_approval_approval_updated_v4(
                _handle_approval_updated_v4,
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

        if event["on_event"].event.object is None:
            raise ValueError("event.event.object is None")

        approval_data = event["on_event"].event.object
        
        # Build variables dictionary
        variables_dict = {
            "approval_code": approval_data.approval_code if approval_data.approval_code else "",
            "approval_id": approval_data.approval_id if approval_data.approval_id else "",
            "timestamp": approval_data.timestamp if approval_data.timestamp else "",
            "version_id": approval_data.version_id if approval_data.version_id else "",
            "form_definition_id": approval_data.form_definition_id if approval_data.form_definition_id else "",
            "widget_group_type": approval_data.widget_group_type if approval_data.widget_group_type is not None else 0,
            "process_obj": approval_data.process_obj if approval_data.process_obj else "",
            "extra": approval_data.extra if approval_data.extra else "",
        }

        return Variables(
            variables=variables_dict,
        )