from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.contact.v3 import P2ContactDepartmentCreatedV3

import lark_oapi as lark
import json


class ContactDepartmentCreatedV3Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle new department creation event.
        
        This event is triggered when a new department is created in the organization.
        """
        event: dict[str, P2ContactDepartmentCreatedV3] = {}

        def _handle_department_created_v3(on_event: P2ContactDepartmentCreatedV3) -> None:
            """
            Handle the department created event.
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
            .register_p2_contact_department_created_v3(
                _handle_department_created_v3,
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

        dept_data = event["on_event"].event.object
        
        # Build variables dictionary with explicit fields
        variables_dict = {
            # Department IDs
            "department_id": dept_data.department_id if dept_data.department_id else "",
            "open_department_id": dept_data.open_department_id if dept_data.open_department_id else "",
            "parent_department_id": dept_data.parent_department_id if dept_data.parent_department_id else "",
            
            # Basic information
            "name": dept_data.name if dept_data.name else "",
            "chat_id": dept_data.chat_id if dept_data.chat_id else "",
            
            # Leadership
            "leader_user_id": dept_data.leader_user_id if dept_data.leader_user_id else "",
            
            # Order and status
            "order": dept_data.order if dept_data.order is not None else 0,
            "status": dept_data.status if dept_data.status else "",
        }
        
        # Add unit IDs as JSON array
        if dept_data.unit_ids:
            variables_dict["unit_ids"] = json.dumps(dept_data.unit_ids, ensure_ascii=False)
        else:
            variables_dict["unit_ids"] = "[]"
        
        # Add leaders list as JSON
        if dept_data.leaders:
            leaders_list = []
            for leader in dept_data.leaders:
                if leader:
                    leader_info = {
                        "leader_type": leader.leaderType if hasattr(leader, 'leaderType') else 0,
                        "leader_id": leader.leaderID if hasattr(leader, 'leaderID') else ""
                    }
                    leaders_list.append(leader_info)
            variables_dict["leaders"] = json.dumps(leaders_list, ensure_ascii=False)
        else:
            variables_dict["leaders"] = "[]"
        
        # Add HRBPs list as JSON
        if dept_data.department_hrbps:
            variables_dict["hrbps"] = json.dumps(dept_data.department_hrbps, ensure_ascii=False)
        else:
            variables_dict["hrbps"] = "[]"

        return Variables(
            variables=variables_dict,
        )