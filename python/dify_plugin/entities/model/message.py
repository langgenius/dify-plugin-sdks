from collections.abc import Sequence
from enum import Enum, StrEnum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, Field, field_validator


class PromptMessageRole(Enum):
    """
    Enum class for prompt message.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

    @classmethod
    def value_of(cls, value: str) -> "PromptMessageRole":
        """
        Get value of given mode.

        :param value: mode value
        :return: mode
        """
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"invalid prompt message type value {value}")


class PromptMessageTool(BaseModel):
    """
    Model class for prompt message tool.
    """

    name: str

    description: str
    parameters: dict


class PromptMessageFunction(BaseModel):
    """
    Model class for prompt message function.
    """

    type: str = "function"
    function: PromptMessageTool


class PromptMessageContentType(StrEnum):
    """
    Enum class for prompt message content type.
    """

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class PromptMessageContent(BaseModel):
    pass


class TextPromptMessageContent(PromptMessageContent):
    """
    Model class for text prompt message content.
    """

    type: Literal[PromptMessageContentType.TEXT] = PromptMessageContentType.TEXT
    data: str


class MultiModalPromptMessageContent(PromptMessageContent):
    """
    Model class for multi-modal prompt message content.
    """

    format: str = Field(default=..., description="the format of multi-modal file")
    base64_data: str = Field(default="", description="the base64 data of multi-modal file")
    url: str = Field(default="", description="the url of multi-modal file")
    mime_type: str = Field(default=..., description="the mime type of multi-modal file")

    @property
    def data(self):
        return self.url or f"data:{self.mime_type};base64,{self.base64_data}"


class VideoPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.VIDEO] = PromptMessageContentType.VIDEO


class AudioPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.AUDIO] = PromptMessageContentType.AUDIO


class ImagePromptMessageContent(MultiModalPromptMessageContent):
    class DETAIL(Enum):
        LOW = "low"
        HIGH = "high"

    type: Literal[PromptMessageContentType.IMAGE] = PromptMessageContentType.IMAGE
    detail: DETAIL = DETAIL.LOW


class DocumentPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.DOCUMENT] = PromptMessageContentType.DOCUMENT


PromptMessageContentUnionTypes = Annotated[
    Union[
        TextPromptMessageContent,
        ImagePromptMessageContent,
        DocumentPromptMessageContent,
        AudioPromptMessageContent,
        VideoPromptMessageContent,
    ],
    Field(discriminator="type"),
]


class PromptMessage(BaseModel):
    """
    Model class for prompt message.
    """

    role: PromptMessageRole
    content: Optional[str | list[PromptMessageContentUnionTypes]] = None
    name: Optional[str] = None

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        return not self.content

    @field_validator("content", mode="before")
    @classmethod
    def transform_content(
        cls, value: list[dict] | Sequence[PromptMessageContent] | str | None
    ) -> Optional[str | list[PromptMessageContent]]:
        """
        Transform content to list of prompt message content.
        """
        if isinstance(value, str):
            return value
        elif isinstance(value, Sequence):
            result = []
            for content in value:
                if isinstance(content, PromptMessageContent):
                    result.append(content)
                    continue
                if not isinstance(content, dict):
                    raise ValueError("invalid prompt message content")
                value_type = content.get("type")
                match value_type:
                    case PromptMessageContentType.TEXT:
                        result.append(TextPromptMessageContent.model_validate(content))
                    case PromptMessageContentType.IMAGE:
                        result.append(ImagePromptMessageContent.model_validate(content))
                    case PromptMessageContentType.AUDIO:
                        result.append(AudioPromptMessageContent.model_validate(content))
                    case PromptMessageContentType.VIDEO:
                        result.append(VideoPromptMessageContent.model_validate(content))
                    case PromptMessageContentType.DOCUMENT:
                        result.append(DocumentPromptMessageContent.model_validate(content))
                    case _:
                        raise ValueError("invalid prompt message content type")
            return result
        return value


class UserPromptMessage(PromptMessage):
    """
    Model class for user prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.USER


def _ensure_field_empty_str(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value


class AssistantPromptMessage(PromptMessage):
    """
    Model class for assistant prompt message.
    """

    class ToolCall(BaseModel):
        """
        Model class for assistant prompt message tool call.
        """

        class ToolCallFunction(BaseModel):
            """
            Model class for assistant prompt message tool call function.
            """

            name: Annotated[str, BeforeValidator(_ensure_field_empty_str)]
            arguments: Annotated[str, BeforeValidator(_ensure_field_empty_str)]

        id: str
        type: Annotated[str, BeforeValidator(_ensure_field_empty_str)]
        function: ToolCallFunction

        @field_validator("id", mode="before")
        @classmethod
        def transform_id_to_str(cls, value) -> str:
            if value is None:
                return ""
            elif not isinstance(value, str):
                return str(value)
            else:
                return value

    role: PromptMessageRole = PromptMessageRole.ASSISTANT
    tool_calls: list[ToolCall] = []

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        return not (not super().is_empty() and not self.tool_calls)


class SystemPromptMessage(PromptMessage):
    """
    Model class for system prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.SYSTEM


class ToolPromptMessage(PromptMessage):
    """
    Model class for tool prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.TOOL
    tool_call_id: str

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        return not (not super().is_empty() and not self.tool_call_id)
