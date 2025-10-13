from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.contact.v3 import P2ContactUserCreatedV3

import lark_oapi as lark
import json


class ContactUserCreatedV3Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle new employee onboarding event.
        
        This event is triggered when a new employee is added to the organization.
        """
        event: dict[str, P2ContactUserCreatedV3] = {}

        def _handle_user_created_v3(on_event: P2ContactUserCreatedV3) -> None:
            """
            Handle the user created event.
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
            .register_p2_contact_user_created_v3(
                _handle_user_created_v3,
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

        user_data = event["on_event"].event.object
        
        # Build variables dictionary with explicit fields
        variables_dict = {
            # User IDs
            "open_id": user_data.open_id if user_data.open_id else "",
            "union_id": user_data.union_id if user_data.union_id else "",
            "user_id": user_data.user_id if user_data.user_id else "",
            
            # Basic information
            "name": user_data.name if user_data.name else "",
            "en_name": user_data.en_name if user_data.en_name else "",
            "nickname": user_data.nickname if user_data.nickname else "",
            
            # Contact information
            "email": user_data.email if user_data.email else "",
            "enterprise_email": user_data.enterprise_email if user_data.enterprise_email else "",
            "mobile": user_data.mobile if user_data.mobile else "",
            "mobile_visible": user_data.mobile_visible if user_data.mobile_visible is not None else False,
            
            # Job information
            "job_title": user_data.job_title if user_data.job_title else "",
            "employee_no": user_data.employee_no if user_data.employee_no else "",
            "employee_type": user_data.employee_type if user_data.employee_type is not None else 0,
            "leader_user_id": user_data.leader_user_id if user_data.leader_user_id else "",
            "job_level_id": user_data.job_level_id if user_data.job_level_id else "",
            "job_family_id": user_data.job_family_id if user_data.job_family_id else "",
            
            # Location and time
            "city": user_data.city if user_data.city else "",
            "country": user_data.country if user_data.country else "",
            "work_station": user_data.work_station if user_data.work_station else "",
            "time_zone": user_data.time_zone if user_data.time_zone else "",
            "join_time": user_data.join_time if user_data.join_time is not None else 0,
            
            # Other information
            "gender": user_data.gender if user_data.gender is not None else 0,
            "is_tenant_manager": user_data.is_tenant_manager if user_data.is_tenant_manager is not None else False,
        }
        
        # Add department IDs as JSON array
        if user_data.department_ids:
            variables_dict["department_ids"] = json.dumps(user_data.department_ids, ensure_ascii=False)
        else:
            variables_dict["department_ids"] = "[]"
        
        # Add status information
        if user_data.status:
            variables_dict["is_frozen"] = user_data.status.is_frozen if user_data.status.is_frozen is not None else False
            variables_dict["is_resigned"] = user_data.status.is_resigned if user_data.status.is_resigned is not None else False
            variables_dict["is_activated"] = user_data.status.is_activated if user_data.status.is_activated is not None else False
        else:
            variables_dict["is_frozen"] = False
            variables_dict["is_resigned"] = False
            variables_dict["is_activated"] = False

        return Variables(
            variables=variables_dict,
        )