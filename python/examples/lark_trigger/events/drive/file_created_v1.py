from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.drive.v1 import P2DriveFileCreatedInFolderV1

import lark_oapi as lark


class DriveFileCreatedV1Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle file creation in drive.
        
        This event is triggered when a new file is created in a folder.
        """
        event: dict[str, P2DriveFileCreatedInFolderV1] = {}

        def _handle_file_created_v1(on_event: P2DriveFileCreatedInFolderV1) -> None:
            """
            Handle the file created event.
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
            .register_p2_drive_file_created_in_folder_v1(
                _handle_file_created_v1,
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
            "file_token": event_data.file_token if event_data.file_token else "",
            "file_type": event_data.file_type if event_data.file_type else "",
            "folder_token": event_data.folder_token if event_data.folder_token else "",
        }
        
        # Add operator information if available
        if event_data.operator_id:
            if event_data.operator_id.open_id:
                variables_dict["creator_open_id"] = event_data.operator_id.open_id
            if event_data.operator_id.user_id:
                variables_dict["creator_user_id"] = event_data.operator_id.user_id
            if event_data.operator_id.union_id:
                variables_dict["creator_union_id"] = event_data.operator_id.union_id

        return Variables(
            variables=variables_dict,
        )