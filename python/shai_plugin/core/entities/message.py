from enum import Enum

from pydantic import BaseModel


class SessionMessage(BaseModel):
    class Type(Enum):
        STREAM = "stream"
        INVOKE = "invoke"
        END = "end"
        ERROR = "error"

    type: Type
    data: dict

    def to_dict(self):
        return {"type": self.type.value, "data": self.data}


class InitializeMessage(BaseModel):
    class Type(Enum):
        HANDSHAKE = "handshake"
        ASSET_CHUNK = "asset_chunk"
        MANIFEST_DECLARATION = "manifest_declaration"
        TOOL_DECLARATION = "tool_declaration"
        MODEL_DECLARATION = "model_declaration"
        ENDPOINT_DECLARATION = "endpoint_declaration"
        AGENT_STRATEGY_DECLARATION = "agent_strategy_declaration"
        END = "end"

    class AssetChunk(BaseModel):
        filename: str
        data: str  # base64 encoded
        end: bool

    class Key(BaseModel):
        key: str

    type: Type
    data: dict | list
