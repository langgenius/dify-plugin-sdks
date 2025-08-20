from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dify_plugin.core.server.__base.request_reader import RequestReader

from dify_plugin.core.server.__base.response_writer import ResponseWriter


class PluginInStreamEvent(Enum):
    Request = "request"
    BackwardInvocationResponse = "backwards_response"

    @classmethod
    def value_of(cls, v: str):
        for e in cls:
            if e.value == v:
                return e
        raise ValueError(f"Invalid value for PluginInStream.Event: {v}")


class PluginInStreamBase:
    def __init__(
        self,
        session_id: str,
        event: PluginInStreamEvent,
        data: dict,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        self.session_id = session_id
        self.event = event
        self.data = data
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.app_id = app_id
        self.endpoint_id = endpoint_id
        self.context = context


class PluginInStream(PluginInStreamBase):
    def __init__(
        self,
        session_id: str,
        event: PluginInStreamEvent,
        data: dict,
        reader: "RequestReader",
        writer: "ResponseWriter",
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ):
        self.reader = reader
        self.writer = writer
        super().__init__(session_id, event, data, conversation_id, message_id, app_id, endpoint_id, context)
