from abc import ABC, abstractmethod

from pydantic import BaseModel

from dify_plugin.core.entities.message import SessionMessage
from dify_plugin.core.server.__base.writer_entities import Event, StreamOutputMessage


class ResponseWriter(ABC):
    """
    Writer for a single plugin request
    """

    @abstractmethod
    def write(self, data: str):
        """
        Write data to the response
        """

    @abstractmethod
    def done(self):
        """
        finish this round
        """

    def put(
        self,
        event: Event,
        session_id: str | None = None,
        data: dict | BaseModel | None = None,
    ):
        """
        serialize the output to the daemon
        """
        if isinstance(data, BaseModel):
            data = data.model_dump()

        self.write(StreamOutputMessage(event=event, session_id=session_id, data=data).model_dump_json())
        self.write("\n\n")

    def error(self, session_id: str | None = None, data: dict | BaseModel | None = None):
        return self.put(Event.ERROR, session_id, data)

    def log(self, data: dict | None = None):
        return self.put(Event.LOG, None, data)

    def heartbeat(self):
        return self.put(Event.HEARTBEAT, None, {})

    def session_message(self, session_id: str | None = None, data: dict | BaseModel | None = None):
        return self.put(Event.SESSION, session_id, data)

    def session_message_text(self, session_id: str | None = None, data: dict | BaseModel | None = None) -> str:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        return StreamOutputMessage(event=Event.SESSION, session_id=session_id, data=data).model_dump_json() + "\n\n"

    def stream_object(self, data: dict | BaseModel) -> SessionMessage:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        return SessionMessage(type=SessionMessage.Type.STREAM, data=data)

    def stream_end_object(self) -> SessionMessage:
        return SessionMessage(type=SessionMessage.Type.END, data={})

    def stream_error_object(self, data: dict | BaseModel) -> SessionMessage:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        return SessionMessage(type=SessionMessage.Type.ERROR, data=data)

    def stream_invoke_object(self, data: dict | BaseModel) -> SessionMessage:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        return SessionMessage(type=SessionMessage.Type.INVOKE, data=data)
