from typing import Any, Mapping
from werkzeug import Request
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event
from lark_oapi.core.http import RawRequest
from lark_oapi.api.calendar.v4 import P2CalendarCalendarEventChangedV4

import lark_oapi as lark
import json


class CalendarEventChangedV4Event(Event):
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Handle calendar event changes.
        
        This event is triggered when a calendar event is created, updated, or deleted.
        """
        event: dict[str, P2CalendarCalendarEventChangedV4] = {}

        def _handle_calendar_event_changed_v4(on_event: P2CalendarCalendarEventChangedV4) -> None:
            """
            Handle the calendar event changed event.
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
            .register_p2_calendar_calendar_event_changed_v4(
                _handle_calendar_event_changed_v4,
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
            "calendar_id": event_data.calendar_id if event_data.calendar_id else "",
            "event_id": event_data.calendar_event_id if event_data.calendar_event_id else "",
            "change_type": event_data.change_type if event_data.change_type else "",
        }
        
        # Add affected users
        if event_data.user_id_list:
            users_list = []
            for user in event_data.user_id_list:
                if user:
                    user_info = {}
                    if user.user_id:
                        user_info["user_id"] = user.user_id
                    if user.open_id:
                        user_info["open_id"] = user.open_id
                    if user.union_id:
                        user_info["union_id"] = user.union_id
                    users_list.append(user_info)
            
            variables_dict["affected_users"] = json.dumps(users_list, ensure_ascii=False)
            variables_dict["affected_users_count"] = str(len(users_list))
        else:
            variables_dict["affected_users"] = "[]"
            variables_dict["affected_users_count"] = "0"
        
        # Add RSVP information
        if event_data.rsvp_infos:
            rsvp_list = []
            for rsvp in event_data.rsvp_infos:
                if rsvp:
                    rsvp_info = {
                        "rsvp_status": rsvp.rsvp_status if rsvp.rsvp_status else "",
                        "from_user_id": rsvp.from_user_id if rsvp.from_user_id else "",
                    }
                    rsvp_list.append(rsvp_info)
            
            variables_dict["rsvp_responses"] = json.dumps(rsvp_list, ensure_ascii=False)
        else:
            variables_dict["rsvp_responses"] = "[]"

        return Variables(
            variables=variables_dict,
        )