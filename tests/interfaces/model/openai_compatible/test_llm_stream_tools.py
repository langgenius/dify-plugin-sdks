import json
from io import BytesIO
from unittest.mock import patch

import pytest
import requests

from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessage,
    SystemPromptMessage,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


def _stream(
    llm: OAICompatLargeLanguageModel,
    deltas: list[dict],
    *,
    prompts: list[PromptMessage] | None = None,
    usage: dict | None = None,
    calling_type: str = "tool_call",
) -> list[LLMResultChunk]:
    frames = [{"choices": [{"delta": delta}]} for delta in deltas]
    frames.append({
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": usage,
    })
    data = "\n\n".join([
        *("data: " + json.dumps(frame) for frame in frames),
        "data: [DONE]",
    ])
    response = requests.Response()
    response.encoding = "utf-8"
    response.raw = BytesIO((data + "\n\n").encode())
    with llm.timing_context():
        return list(
            llm._handle_generate_stream_response(
                model="model",
                credentials={"mode": "chat", "function_calling_type": calling_type},
                response=response,
                prompt_messages=prompts or [UserPromptMessage(content="Hello")],
            )
        )


@pytest.mark.parametrize("id_only_first_chunk", [False, True])
def test_stream_keeps_parallel_tool_arguments_with_their_indices(
    id_only_first_chunk: bool,
) -> None:
    headers = [
        {"index": 0, "id": "call-paris", "type": "function"},
        {"index": 1, "id": "call-berlin", "type": "function"},
    ]
    functions = [
        {"index": 0, "function": {"name": "weather", "arguments": '{"city":"Pa'}},
        {"index": 1, "function": {"name": "weather", "arguments": '{"city":"Be'}},
    ]
    if not id_only_first_chunk:
        for header, function in zip(headers, functions, strict=True):
            header.update(function)
    deltas = [
        {"reasoning_content": "Choose two cities"},
        {},
        {"tool_calls": headers},
    ]
    if id_only_first_chunk:
        deltas.append({"tool_calls": functions})
    deltas.extend([
        {},
        {"tool_calls": [{"index": 1, "function": {"arguments": 'rlin"}'}}]},
        {"reasoning_content": None},
        {"tool_calls": [{"index": 0, "function": {"arguments": 'ris"}'}}]},
    ])

    chunks = _stream(
        OAICompatLargeLanguageModel([]),
        deltas,
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )

    assert "".join(chunk.delta.message.content for chunk in chunks) == (
        "<think>\nChoose two cities\n</think>"
    )
    tool_chunks = [chunk for chunk in chunks if chunk.delta.message.tool_calls]
    assert len(tool_chunks) == 1
    assert tool_chunks[0] is chunks[-1]
    assert tool_chunks[0].delta.usage is not None
    assert tool_chunks[0].delta.usage.total_tokens == 30
    assert tool_chunks[0].delta.finish_reason == "stop"
    assert {
        call.id: (call.function.name, json.loads(call.function.arguments))
        for call in tool_chunks[0].delta.message.tool_calls
    } == {
        "call-paris": ("weather", {"city": "Paris"}),
        "call-berlin": ("weather", {"city": "Berlin"}),
    }


def test_stream_keeps_legacy_function_arguments_across_heartbeats() -> None:
    chunks = _stream(
        OAICompatLargeLanguageModel([]),
        [
            {"reasoning": "Check the weather"},
            {},
            {"function_call": {"name": "weather", "arguments": '{"city":"'}},
            {},
            {"function_call": {"arguments": 'Paris"}'}},
        ],
        calling_type="function_call",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )

    calls = [call for chunk in chunks for call in chunk.delta.message.tool_calls]
    assert len(calls) == 1
    assert calls[0].function.name == "weather"
    assert json.loads(calls[0].function.arguments) == {"city": "Paris"}
    assert "".join(chunk.delta.message.content for chunk in chunks) == (
        "<think>\nCheck the weather\n</think>"
    )


@pytest.mark.parametrize(
    "usage", [None, {"prompt_tokens": None, "completion_tokens": None}]
)
def test_stream_missing_usage_counts_all_prompt_messages_and_text_parts(
    usage: dict | None,
) -> None:
    first_part = "First part of the user question. " * 10
    second_part = "Second part of the user question. " * 10
    llm = OAICompatLargeLanguageModel([])
    with patch.object(llm, "_get_num_tokens_by_gpt2", side_effect=len) as tokenize:
        chunks = _stream(
            llm,
            [{"content": "Answer"}],
            usage=usage,
            prompts=[
                SystemPromptMessage(content="Instructions"),
                UserPromptMessage(
                    content=[
                        TextPromptMessageContent(data=first_part),
                        ImagePromptMessageContent(
                            format="png",
                            mime_type="image/png",
                            url="https://example.com/image.png",
                        ),
                        TextPromptMessageContent(data=second_part),
                    ]
                ),
            ],
        )

    tokenized_text = "".join(call.args[0] for call in tokenize.call_args_list)
    assert first_part in tokenized_text
    assert second_part in tokenized_text
    assert "https://example.com/image.png" not in tokenized_text
    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.prompt_tokens >= len("Instructions" + first_part + second_part)
    assert usage.completion_tokens == len("Answer")


def test_stream_completion_usage_estimates_the_sent_prompt() -> None:
    response = requests.Response()
    response.encoding = "utf-8"
    response.raw = BytesIO(
        b'data: {"choices": [{"text": "Answer", "finish_reason": "stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    llm = OAICompatLargeLanguageModel([])
    with (
        llm.timing_context(),
        patch.object(llm, "_get_num_tokens_by_gpt2", side_effect=len),
    ):
        chunks = list(
            llm._handle_generate_stream_response(
                model="model",
                credentials={"mode": "completion"},
                response=response,
                prompt_messages=[
                    UserPromptMessage(content="Question"),
                    UserPromptMessage(content="Only the first message is sent"),
                ],
            )
        )

    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.prompt_tokens == len("Question")
    assert usage.completion_tokens == len("Answer")


def test_stream_missing_usage_counts_tool_history_with_null_assistant_content() -> None:
    arguments = json.dumps({"query": "Previous question " * 10})
    tool = AssistantPromptMessage.ToolCall(
        id="call-history",
        type="function",
        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="search", arguments=arguments
        ),
    )
    llm = OAICompatLargeLanguageModel([])
    with patch.object(llm, "_get_num_tokens_by_gpt2", side_effect=len) as tokenize:
        chunks = _stream(
            llm,
            [{"content": "Answer"}],
            prompts=[
                AssistantPromptMessage(content=None, tool_calls=[tool]),
                ToolPromptMessage(content="Search result", tool_call_id="call-history"),
                UserPromptMessage(content="Summarize the result"),
            ],
        )

    tokenized_text = "".join(call.args[0] for call in tokenize.call_args_list)
    assert "Previous question " * 10 in tokenized_text
    assert "Search result" in tokenized_text
    assert "Summarize the result" in tokenized_text
    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.prompt_tokens >= len(arguments)


@pytest.mark.parametrize("calling_type", ["tool_call", "function_call"])
def test_stream_missing_usage_counts_tool_output(calling_type: str) -> None:
    query = "Current question " * 10
    function = {"name": "search", "arguments": json.dumps({"query": query})}
    delta = (
        {"tool_calls": [{"index": 0, "id": "call", "function": function}]}
        if calling_type == "tool_call"
        else {"function_call": function}
    )
    llm = OAICompatLargeLanguageModel([])
    with patch.object(llm, "_get_num_tokens_by_gpt2", side_effect=len) as tokenize:
        chunks = _stream(llm, [delta], calling_type=calling_type)

    assert query in "".join(call.args[0] for call in tokenize.call_args_list)
    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.completion_tokens >= len(query)


def test_stream_uses_reported_usage_without_local_estimation() -> None:
    llm = OAICompatLargeLanguageModel([])
    with patch.object(
        llm,
        "_get_num_tokens_by_gpt2",
        side_effect=AssertionError("Unexpected estimate"),
    ):
        chunks = _stream(
            llm,
            [{"reasoning_content": "Think"}, {}, {"content": "Answer"}],
            usage={"prompt_tokens": 40, "completion_tokens": 30},
        )

    usage = chunks[-1].delta.usage
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (
        40,
        30,
        70,
    )
