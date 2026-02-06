from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk, LLMResultChunkDelta, LLMUsage
from dify_plugin.entities.model.message import AssistantPromptMessage, TextPromptMessageContent


def test_assistant_message_opaque_body_roundtrip():
    message = AssistantPromptMessage(
        content=[TextPromptMessageContent(data="Hello", opaque_body={"segment_id": 1})],
        opaque_body={"provider_message_id": "msg_123"},
    )

    assert message.opaque_body == {"provider_message_id": "msg_123"}
    assert isinstance(message.content, list)
    assert message.content[0].opaque_body == {"segment_id": 1}


def test_build_llm_result_chunk_with_prompt_messages():
    chunk = LLMResultChunk(
        model="test",
        prompt_messages=[AssistantPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")])],
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")]),
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


def test_build_llm_result_with_prompt_messages():
    result = LLMResult(
        model="test",
        prompt_messages=[AssistantPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")])],
        message=AssistantPromptMessage(content=[TextPromptMessageContent(data="Hello, World!")]),
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
