import threading
from werkzeug import Request, Response

from dify_plugin.entities.trigger import EventDispatch, Subscription
from dify_plugin.errors.trigger import TriggerDispatchError
from dify_plugin.interfaces.trigger import Trigger
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    P2ImChatAccessEventBotP2pChatEnteredV1, 
    P2ImMessageReceiveV1, 
    P2ImChatMemberBotAddedV1,
    P2ImChatMemberUserAddedV1,
    P2ImChatMemberUserDeletedV1,
    P2ImMessageReactionCreatedV1,
    P2ImMessageMessageReadV1,
)
from lark_oapi.api.calendar.v4 import P2CalendarCalendarEventChangedV4
from lark_oapi.api.approval.v4 import P2ApprovalApprovalUpdatedV4
from lark_oapi.api.drive.v1 import P2DriveFileCreatedInFolderV1
from lark_oapi.api.contact.v3 import P2ContactUserCreatedV3, P2ContactDepartmentCreatedV3
from lark_oapi.core.http import RawRequest


"""
cache the response of the event, so that the response will not be cached by the browser
key: thread_id
value: events_to_dispatch
"""
response_cache_map: dict[int, list[str]] = {}


class LarkTrigger(Trigger):
    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        """
        Handle Lark event dispatch.
        """
        encrypt_key = subscription.properties.get("lark_encrypt_key")
        verification_token = subscription.properties.get("lark_verification_token")

        if not encrypt_key or not verification_token:
            raise TriggerDispatchError("Encrypt key or verification token not found")

        self.handler = (
            lark.EventDispatcherHandler.builder(
                encrypt_key,
                verification_token,
            )
            # IM Events
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
                self._handle_p2p_chat_entered_event,
            )
            .register_p2_im_message_receive_v1(
                self._handle_message_received_event,
            )
            .register_p2_im_chat_member_bot_added_v1(
                self._handle_chat_member_bot_added_event,
            )
            .register_p2_im_chat_member_user_added_v1(
                self._handle_chat_member_user_added_event,
            )
            .register_p2_im_chat_member_user_deleted_v1(
                self._handle_chat_member_user_removed_event,
            )
            .register_p2_im_message_reaction_created_v1(
                self._handle_message_reaction_added_event,
            )
            .register_p2_im_message_message_read_v1(
                self._handle_message_read_event,
            )
            # Calendar Events
            .register_p2_calendar_calendar_event_changed_v4(
                self._handle_calendar_event_changed_event,
            )
            # Approval Events
            .register_p2_approval_approval_updated_v4(
                self._handle_approval_updated_event,
            )
            # Drive Events
            .register_p2_drive_file_created_in_folder_v1(
                self._handle_drive_file_created_event,
            )
            # Contact Events
            .register_p2_contact_user_created_v3(
                self._handle_contact_user_created_event,
            )
            .register_p2_contact_department_created_v3(
                self._handle_contact_department_created_event,
            )
            .build()
        )

        raw_request = RawRequest()
        raw_request.uri = request.url
        raw_request.headers = request.headers
        raw_request.body = request.get_data()

        events_to_dispatch = []
        response_cache_map[threading.get_ident()] = []

        try:
            """
            Do the event dispatch, and cache the response of the event
            """
            raw_response = self.handler.do(raw_request)
        finally:
            events_to_dispatch = response_cache_map.pop(threading.get_ident())

        return EventDispatch(
            response=Response(
                status=raw_response.status_code,
                headers=raw_response.headers,
                response=raw_response.content,
            ),
            events=events_to_dispatch,
        )

    def _handle_p2p_chat_entered_event(self, event: P2ImChatAccessEventBotP2pChatEnteredV1) -> None:
        """
        Handle P2P chat entered event.

        :param event: P2P chat entered event
        """
        response_cache_map[threading.get_ident()].append("p2p_chat_entered")

    def _handle_message_received_event(self, event: P2ImMessageReceiveV1) -> None:
        """
        Handle message received event.

        :param event: Message received event
        """
        response_cache_map[threading.get_ident()].append("p2p_im_message_receive_v1")

    def _handle_chat_member_bot_added_event(self, event: P2ImChatMemberBotAddedV1) -> None:
        """
        Handle chat member bot added event.

        :param event: Chat member bot added event
        """
        response_cache_map[threading.get_ident()].append("p2p_im_chat_member_bot_added_v1")
    
    def _handle_chat_member_user_added_event(self, event: P2ImChatMemberUserAddedV1) -> None:
        """
        Handle chat member user added event.

        :param event: Chat member user added event
        """
        response_cache_map[threading.get_ident()].append("chat_member_user_added_v1")
    
    def _handle_chat_member_user_removed_event(self, event: P2ImChatMemberUserDeletedV1) -> None:
        """
        Handle chat member user removed event.

        :param event: Chat member user removed event
        """
        response_cache_map[threading.get_ident()].append("chat_member_user_removed_v1")
    
    def _handle_message_reaction_added_event(self, event: P2ImMessageReactionCreatedV1) -> None:
        """
        Handle message reaction added event.

        :param event: Message reaction added event
        """
        response_cache_map[threading.get_ident()].append("message_reaction_added_v1")
    
    def _handle_message_read_event(self, event: P2ImMessageMessageReadV1) -> None:
        """
        Handle message read event.

        :param event: Message read event
        """
        response_cache_map[threading.get_ident()].append("message_read_v1")
    
    def _handle_calendar_event_changed_event(self, event: P2CalendarCalendarEventChangedV4) -> None:
        """
        Handle calendar event changed.

        :param event: Calendar event changed event
        """
        response_cache_map[threading.get_ident()].append("calendar_event_changed_v4")
    
    def _handle_approval_updated_event(self, event: P2ApprovalApprovalUpdatedV4) -> None:
        """
        Handle approval updated event.

        :param event: Approval updated event
        """
        response_cache_map[threading.get_ident()].append("approval_updated_v4")
    
    def _handle_drive_file_created_event(self, event: P2DriveFileCreatedInFolderV1) -> None:
        """
        Handle drive file created event.

        :param event: Drive file created event
        """
        response_cache_map[threading.get_ident()].append("file_created_v1")
    
    def _handle_contact_user_created_event(self, event: P2ContactUserCreatedV3) -> None:
        """
        Handle contact user created event.

        :param event: Contact user created event
        """
        response_cache_map[threading.get_ident()].append("user_created_v3")
    
    def _handle_contact_department_created_event(self, event: P2ContactDepartmentCreatedV3) -> None:
        """
        Handle contact department created event.

        :param event: Contact department created event
        """
        response_cache_map[threading.get_ident()].append("department_created_v3")
