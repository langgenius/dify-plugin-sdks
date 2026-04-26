from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event

from .._shared import dispatch_single_event


class ContactUserDeletedV3Event(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Handle employee deletion/departure event.

        This event is triggered when an employee is deleted from the
        organization or leaves.

        Returns:
            The return value.

        Raises:
            ValueError: If input values are invalid.
        """
        event_data = dispatch_single_event(
            request,
            self.runtime,
            lambda builder: builder.register_p2_contact_user_deleted_v3,
        ).event
        if event_data is None:
            raise ValueError("event_data is None")

        # Build variables dictionary with basic user information
        variables_dict = {}

        # Extract current (deleted) user information
        if event_data.object:
            user_data = event_data.object
            variables_dict.update({
                "user_id": user_data.user_id or "",
                "open_id": user_data.open_id or "",
                "union_id": user_data.union_id or "",
                "name": user_data.name or "",
                "en_name": user_data.en_name or "",
                "email": user_data.email or "",
                "mobile": user_data.mobile or "",
                "employee_no": user_data.employee_no or "",
                "employee_type": str(user_data.employee_type)
                if user_data.employee_type is not None
                else "0",
            })

            # Add department IDs
            if user_data.department_ids:
                variables_dict["department_ids"] = list(user_data.department_ids)
            else:
                variables_dict["department_ids"] = []

        # Extract previous user information (before deletion)
        if event_data.old_object:
            old_data = event_data.old_object
            old_user_info = {
                "open_id": old_data.open_id or "",
                "department_ids": list(old_data.department_ids)
                if old_data.department_ids
                else [],
            }
            variables_dict["old_user_info"] = old_user_info
        else:
            variables_dict["old_user_info"] = {}

        return Variables(
            variables=variables_dict,
        )
