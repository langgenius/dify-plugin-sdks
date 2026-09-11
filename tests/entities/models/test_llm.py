import pytest

from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessage,
    PromptMessageContentUnionTypes,
    PromptMessageRole,
    TextPromptMessageContent,
)


class TestLLMResultChunk:
    def test_init(self) -> None:
        model = "gpt-4o"
        delta = LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(
                content="Hello, World!", role=PromptMessageRole.ASSISTANT
            ),
        )
        prompt_message = PromptMessage(
            role=PromptMessageRole.USER,
            content="Hello",
        )
        LLMResultChunk(model=model, delta=delta)

        LLMResultChunk(model=model, delta=delta, system_fingerprint="123")

        LLMResultChunk(
            model=model, prompt_messages=[], delta=delta, system_fingerprint="123"
        )

        LLMResultChunk(
            model=model,
            prompt_messages=[prompt_message],
            delta=delta,
            system_fingerprint="123",
        )


class TestLLMResult:
    def test_init(self) -> None:
        model = "gpt-4o"
        assistant_message = AssistantPromptMessage(
            content="Hello, World!", role=PromptMessageRole.ASSISTANT
        )
        usage = LLMUsage.empty_usage()
        prompt_message = PromptMessage(
            role=PromptMessageRole.USER,
            content="Hello",
        )

        LLMResult(model=model, message=assistant_message, usage=usage)

        LLMResult(
            model=model,
            prompt_messages=[],
            message=assistant_message,
            usage=usage,
            system_fingerprint="123",
        )

        LLMResult(
            model=model,
            prompt_messages=[prompt_message],
            message=assistant_message,
            usage=usage,
            system_fingerprint="123",
        )


def chunk_with(
    content: str | list[PromptMessageContentUnionTypes] | None,
    tool_calls: list[AssistantPromptMessage.ToolCall] | None = None,
) -> LLMResultChunk:
    return LLMResultChunk(
        model="gpt-4o",
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(
                content=content,
                tool_calls=tool_calls or [],
            ),
        ),
    )


TOOL_CALL = AssistantPromptMessage.ToolCall(
    id="call-1",
    type="function",
    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
        name="search",
        arguments="{}",
    ),
)

EMPTY_IMAGE = ImagePromptMessageContent(format="png", mime_type="image/png")


class TestCarriesFirstToken:
    """The SDK half of a rule the daemon enforces again one hop up; the two must
    agree, or the same stream is judged differently at each layer."""

    @pytest.mark.parametrize(
        "chunk",
        [
            chunk_with(None),
            chunk_with(""),
            chunk_with([]),
            chunk_with([TextPromptMessageContent(data="")]),
            chunk_with([EMPTY_IMAGE]),
        ],
    )
    def test_an_empty_envelope_is_not_a_first_token(
        self, chunk: LLMResultChunk
    ) -> None:
        assert chunk.carries_first_token() is False

    @pytest.mark.parametrize(
        "chunk",
        [
            chunk_with("hi"),
            chunk_with([TextPromptMessageContent(data="hi")]),
            chunk_with([EMPTY_IMAGE, TextPromptMessageContent(data="hi")]),
            chunk_with([EMPTY_IMAGE.model_copy(update={"url": "https://x/y.png"})]),
            chunk_with([EMPTY_IMAGE.model_copy(update={"base64_data": "aGk="})]),
            chunk_with("", tool_calls=[TOOL_CALL]),
        ],
    )
    def test_generated_content_is_a_first_token(self, chunk: LLMResultChunk) -> None:
        assert chunk.carries_first_token() is True
