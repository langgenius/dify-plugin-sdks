import base64
import contextlib
import uuid
from collections.abc import Mapping
from enum import Enum
from typing import Any, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from dify_plugin.entities.provider_config import LogMetadata


class InvokeMessage(BaseModel):
    class TextMessage(BaseModel):
        text: str

        def to_dict(self):
            return {"text": self.text}

    class JsonMessage(BaseModel):
        json_object: Mapping | list

        def to_dict(self):
            return {"json_object": self.json_object}

    class BlobMessage(BaseModel):
        blob: bytes

    class BlobChunkMessage(BaseModel):
        id: str = Field(..., description="The id of the blob")
        sequence: int = Field(..., description="The sequence of the chunk")
        total_length: int = Field(..., description="The total length of the blob")
        blob: bytes = Field(..., description="The blob data of the chunk")
        end: bool = Field(..., description="Whether the chunk is the last chunk")

    class VariableMessage(BaseModel):
        variable_name: str = Field(
            ...,
            description="The name of the variable, only supports root-level variables",
        )
        variable_value: Any = Field(..., description="The value of the variable")
        stream: bool = Field(default=False, description="Whether the variable is streamed")

        @model_validator(mode="before")
        @classmethod
        def validate_variable_value_and_stream(cls, values):
            # skip validation if values is not a dict
            if not isinstance(values, dict):
                return values

            if values.get("stream") and not isinstance(values.get("variable_value"), str):
                raise ValueError("When 'stream' is True, 'variable_value' must be a string.")
            return values

    class LogMessage(BaseModel):
        class LogStatus(Enum):
            START = "start"
            ERROR = "error"
            SUCCESS = "success"

        id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The id of the log")
        label: str = Field(..., description="The label of the log")
        parent_id: Optional[str] = Field(default=None, description="Leave empty for root log")
        error: Optional[str] = Field(default=None, description="The error message")
        status: LogStatus = Field(..., description="The status of the log")
        data: Mapping[str, Any] = Field(..., description="Detailed log data")
        metadata: Optional[Mapping[LogMetadata, Any]] = Field(default=None, description="The metadata of the log")

    class RetrieverResourceMessage(BaseModel):
        class RetrieverResource(BaseModel):
            """
            Model class for retriever resource.
            """

            position: Optional[int] = None
            dataset_id: Optional[str] = None
            dataset_name: Optional[str] = None
            document_id: Optional[str] = None
            document_name: Optional[str] = None
            data_source_type: Optional[str] = None
            segment_id: Optional[str] = None
            retriever_from: Optional[str] = None
            score: Optional[float] = None
            hit_count: Optional[int] = None
            word_count: Optional[int] = None
            segment_position: Optional[int] = None
            index_node_hash: Optional[str] = None
            content: Optional[str] = None
            page: Optional[int] = None
            doc_metadata: Optional[dict] = None

        retriever_resources: list[RetrieverResource] = Field(..., description="retriever resources")
        context: str = Field(..., description="context")

    class MessageType(Enum):
        TEXT = "text"
        FILE = "file"
        BLOB = "blob"
        JSON = "json"
        LINK = "link"
        IMAGE = "image"
        IMAGE_LINK = "image_link"
        VARIABLE = "variable"
        BLOB_CHUNK = "blob_chunk"
        LOG = "log"
        RETRIEVER_RESOURCES = "retriever_resources"

    type: MessageType
    # TODO: pydantic will validate and construct the message one by one, until it encounters a correct type
    # we need to optimize the construction process
    message: (
        TextMessage
        | JsonMessage
        | VariableMessage
        | BlobMessage
        | BlobChunkMessage
        | LogMessage
        | RetrieverResourceMessage
        | None
    )
    meta: Optional[dict] = None

    @field_validator("message", mode="before")
    @classmethod
    def decode_blob_message(cls, v):
        if isinstance(v, dict) and "blob" in v:
            with contextlib.suppress(Exception):
                v["blob"] = base64.b64decode(v["blob"])
        return v

    @field_serializer("message")
    def serialize_message(self, v):
        if isinstance(v, self.BlobMessage):
            return {"blob": base64.b64encode(v.blob).decode("utf-8")}
        elif isinstance(v, self.BlobChunkMessage):
            return {
                "id": v.id,
                "sequence": v.sequence,
                "total_length": v.total_length,
                "blob": base64.b64encode(v.blob).decode("utf-8"),
                "end": v.end,
            }
        return v
