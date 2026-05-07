from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class ContactUserCreatedV3Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle new employee onboarding event.

        This event is triggered when a new employee is added to the organization.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_wrapper = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_contact_user_created_v3,
        )
        if event_wrapper.event is None:
            msg = "event_wrapper.event is None"
            raise ValueError(msg)

        event_data = event_wrapper.event
        if event_data.object is None:
            msg = "event_data.object is None"
            raise ValueError(msg)

        user_data = event_data.object

        # Build variables dictionary with explicit fields
        variables_dict = {
            # User IDs
            "open_id": user_data.open_id or "",
            "union_id": user_data.union_id or "",
            "user_id": user_data.user_id or "",
            # Basic information
            "name": user_data.name or "",
            "en_name": user_data.en_name or "",
            "nickname": user_data.nickname or "",
            # Contact information
            "email": user_data.email or "",
            "enterprise_email": user_data.enterprise_email or "",
            "mobile": user_data.mobile or "",
            "mobile_visible": user_data.mobile_visible
            if user_data.mobile_visible is not None
            else False,
            # Job information
            "job_title": user_data.job_title or "",
            "employee_no": user_data.employee_no or "",
            "employee_type": user_data.employee_type
            if user_data.employee_type is not None
            else 0,
            "leader_user_id": user_data.leader_user_id or "",
            "job_level_id": user_data.job_level_id or "",
            "job_family_id": user_data.job_family_id or "",
            # Location and time
            "city": user_data.city or "",
            "country": user_data.country or "",
            "work_station": user_data.work_station or "",
            "time_zone": user_data.time_zone or "",
            "join_time": user_data.join_time if user_data.join_time is not None else 0,
            # Other information
            "gender": user_data.gender if user_data.gender is not None else 0,
            "is_tenant_manager": user_data.is_tenant_manager
            if user_data.is_tenant_manager is not None
            else False,
        }

        # Add department IDs as array
        if user_data.department_ids:
            variables_dict["department_ids"] = list(user_data.department_ids)
        else:
            variables_dict["department_ids"] = []

        # Add status information
        if user_data.status:
            variables_dict["is_frozen"] = (
                user_data.status.is_frozen
                if user_data.status.is_frozen is not None
                else False
            )
            variables_dict["is_resigned"] = (
                user_data.status.is_resigned
                if user_data.status.is_resigned is not None
                else False
            )
            variables_dict["is_activated"] = (
                user_data.status.is_activated
                if user_data.status.is_activated is not None
                else False
            )
        else:
            variables_dict["is_frozen"] = False
            variables_dict["is_resigned"] = False
            variables_dict["is_activated"] = False

        return Variables(
            variables=variables_dict,
        )
