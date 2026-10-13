from unittest.mock import Mock

import pytest

from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMResultChunkWithStructuredOutput,
    LLMResultWithStructuredOutput,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    TextPromptMessageContent,
)
from tests.interfaces.model.utils import StubLLM


def test_assistant_message_opaque_body_roundtrip() -> None:
    message = AssistantPromptMessage(
        content=[TextPromptMessageContent(data="Hello", opaque_body={"segment_id": 1})],
        opaque_body={"provider_message_id": "msg_123"},
    )

    assert message.opaque_body == {"provider_message_id": "msg_123"}
    assert isinstance(message.content, list)
    assert message.content[0].opaque_body == {"segment_id": 1}


def test_build_llm_result_chunk_with_prompt_messages() -> None:
    chunk = LLMResultChunk(
        model="test",
        prompt_messages=[
            AssistantPromptMessage(
                content=[TextPromptMessageContent(data="Hello, World!")]
            )
        ],
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(
                content=[TextPromptMessageContent(data="Hello, World!")]
            ),
        ),
    )
    assert isinstance(chunk.prompt_messages, list)
    """
    NOTE:
    - https://github.com/langgenius/dify/issues/17799
    - https://github.com/langgenius/dify-official-plugins/issues/648

    The `prompt_messages` field is deprecated, but to keep backward compatibility
    we need to always set it to an empty list.
    """
    assert len(chunk.prompt_messages) == 0


def test_build_llm_result_with_prompt_messages() -> None:
    result = LLMResult(
        model="test",
        prompt_messages=[
            AssistantPromptMessage(
                content=[TextPromptMessageContent(data="Hello, World!")]
            )
        ],
        message=AssistantPromptMessage(
            content=[TextPromptMessageContent(data="Hello, World!")]
        ),
        usage=LLMUsage.empty_usage(),
    )

    assert isinstance(result.prompt_messages, list)
    """
    NOTE:
    - https://github.com/langgenius/dify/issues/17799
    - https://github.com/langgenius/dify-official-plugins/issues/648

    The `prompt_messages` field is deprecated, but to keep backward compatibility
    we need to always set it to an empty list.
    """
    assert len(result.prompt_messages) == 0


@pytest.mark.parametrize("stream", [False, True])
def test_public_llm_invocation_converts_complete_result_to_one_chunk(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    message = AssistantPromptMessage(
        content="answer",
        opaque_body={"provider_id": "message-1"},
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "weather", "arguments": '{"city":"Paris"}'},
            }
        ],
    )
    usage = LLMUsage.empty_usage().model_copy(
        update={
            "prompt_tokens": 5,
            "completion_tokens": 7,
            "total_tokens": 12,
        }
    )
    result = LLMResult(
        model="resolved-model",
        message=message,
        usage=usage,
        system_fingerprint="provider-v1",
    )
    llm = StubLLM([])
    provider = Mock(return_value=result)
    monkeypatch.setattr(llm, "_invoke", provider)
    expected = result.model_copy(deep=True)

    chunks = list(llm.invoke("requested-model", {}, [], stream=stream))

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.model == "resolved-model"
    assert chunk.system_fingerprint == "provider-v1"
    assert chunk.delta.index == 0
    assert chunk.delta.message == expected.message
    assert chunk.delta.usage == expected.usage
    assert chunk.delta.finish_reason is None
    assert provider.call_args.kwargs["stream"] is stream
    assert llm.started_at == 0


def test_structured_result_conversion_preserves_parsed_output() -> None:
    result = LLMResultWithStructuredOutput(
        model="model",
        message=AssistantPromptMessage(content='{"answer":42}'),
        usage=LLMUsage.empty_usage(),
        system_fingerprint="provider-v1",
        structured_output={"answer": 42},
    )

    expected = result.model_copy(deep=True)
    chunk = result.to_llm_result_chunk_with_structured_output()
    restored = LLMResultChunkWithStructuredOutput.model_validate_json(
        chunk.model_dump_json()
    )

    assert restored.structured_output == {"answer": 42}
    assert restored.delta.message == expected.message
    assert restored.delta.usage == expected.usage
    assert restored.system_fingerprint == expected.system_fingerprint
    assert restored.model == expected.model
