from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dify_plugin.core.server.__base.request_reader import RequestReader
    from dify_plugin.core.server.__base.response_writer import ResponseWriter


class PluginInStreamEvent(Enum):
    Request = "request"
    BackwardInvocationResponse = "backwards_response"

    @classmethod
    def value_of(cls, v: str) -> "PluginInStreamEvent":
        return cls(v)


@dataclass(frozen=True, slots=True)
class PluginInStreamBase:
    session_id: str
    event: PluginInStreamEvent
    data: dict
    conversation_id: str | None = None
    message_id: str | None = None
    app_id: str | None = None
    endpoint_id: str | None = None
    context: dict | None = None


@dataclass(frozen=True, slots=True, init=False)
class PluginInStream(PluginInStreamBase):
    reader: "RequestReader"
    writer: "ResponseWriter"

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
    ) -> None:
        object.__setattr__(self, "reader", reader)
        object.__setattr__(self, "writer", writer)
        PluginInStreamBase.__init__(
            self,
            session_id,
            event,
            data,
            conversation_id,
            message_id,
            app_id,
            endpoint_id,
            context,
        )
