import base64
import contextlib
import uuid
from collections.abc import Mapping
from enum import Enum
from typing import Any

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
        parent_id: str | None = Field(default=None, description="Leave empty for root log")
        error: str | None = Field(default=None, description="The error message")
        status: LogStatus = Field(..., description="The status of the log")
        data: Mapping[str, Any] = Field(..., description="Detailed log data")
        metadata: Mapping[LogMetadata, Any] | None = Field(default=None, description="The metadata of the log")

    class RetrieverResourceMessage(BaseModel):
        class RetrieverResource(BaseModel):
            """
            Model class for retriever resource.
            """

            position: int | None = None
            dataset_id: str | None = None
            dataset_name: str | None = None
            document_id: str | None = None
            document_name: str | None = None
            data_source_type: str | None = None
            segment_id: str | None = None
            retriever_from: str | None = None
            score: float | None = None
            hit_count: int | None = None
            word_count: int | None = None
            segment_position: int | None = None
            index_node_hash: str | None = None
            content: str | None = None
            page: int | None = None
            doc_metadata: dict | None = None

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
    meta: dict | None = None

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
