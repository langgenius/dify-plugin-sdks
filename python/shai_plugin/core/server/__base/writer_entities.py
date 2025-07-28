from enum import Enum

from pydantic import BaseModel


class Event(Enum):
    LOG = "log"
    ERROR = "error"
    SESSION = "session"
    HEARTBEAT = "heartbeat"


class StreamOutputMessage(BaseModel):
    event: Event
    session_id: str | None
    data: dict | BaseModel | None
