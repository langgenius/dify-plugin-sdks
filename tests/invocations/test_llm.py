import json
from collections.abc import Generator
from copy import deepcopy

import pytest
from pydantic import JsonValue, ValidationError

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import Session
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    LLMResultChunkWithStructuredOutput,
    LLMResultWithStructuredOutput,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessageTool,
    TextPromptMessageContent,
    UserPromptMessage,
)
from dify_plugin.invocations.model.llm import LLMInvocation, SummaryInvocation
from dify_plugin.invocations.model.llm_structured_output import (
    LLMStructuredOutputInvocation,
)
from tests.http_server import HTTPServerFactory, Response
from tests.invocations.conftest import RecordInvocation


@pytest.fixture
def llm_response() -> dict:
    return {
        "model": "resolved-model",
        "system_fingerprint": "provider-revision",
        "delta": {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"query":"文档"}'},
                    }
                ],
                "opaque_body": {"provider_state": ["retain-for-next-turn"]},
            },
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
                "prompt_unit_price": "0.1",
                "prompt_price_unit": "0.01",
                "prompt_price": "0.005",
                "completion_unit_price": "0.2",
                "completion_price_unit": "0.01",
                "completion_price": "0.004",
                "total_price": "0.009",
                "currency": "USD",
                "latency": 1.25,
            },
            "finish_reason": "tool_calls",
        },
        "structured_output": {},
    }


@pytest.mark.parametrize(
    ("invocation_type", "response_type", "invoke_type"),
    [
        (LLMInvocation, LLMResultChunk, InvokeType.LLM),
        (
            LLMStructuredOutputInvocation,
            LLMResultChunkWithStructuredOutput,
            InvokeType.LLMStructuredOutput,
        ),
    ],
)
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("dict_config", [False, True])
def test_llm_preserves_result_and_request(
    record_invocation: RecordInvocation,
    llm_response: dict,
    invocation_type: type[LLMInvocation | LLMStructuredOutputInvocation],
    response_type: type[LLMResultChunk | LLMResultChunkWithStructuredOutput],
    invoke_type: InvokeType,
    stream: bool,
    dict_config: bool,
) -> None:
    invocation = invocation_type()
    recorded = record_invocation(invocation, [llm_response])
    configuration = {
        "provider": "provider",
        "model": "requested-model",
        "mode": "chat",
        "completion_params": {"temperature": 0.2},
    }
    config = deepcopy(configuration) if dict_config else LLMModelConfig(**configuration)
    tool = PromptMessageTool(
        name="search", description="Search", parameters={"type": "object"}
    )
    arguments = {
        "model_config": config,
        "prompt_messages": [UserPromptMessage(content="hello")],
        "tools": [tool],
        "stop": ["stop"],
        "stream": stream,
    }
    expected = {
        **configuration,
        "model_type": "llm",
        "prompt_messages": [{"role": "user", "content": "hello", "name": None}],
        "tools": [
            {
                "name": "search",
                "description": "Search",
                "parameters": {"type": "object"},
            }
        ],
        "stop": ["stop"],
        "stream": stream,
    }
    if isinstance(invocation, LLMStructuredOutputInvocation):
        arguments["structured_output_schema"] = {"type": "object", "properties": {}}
        expected["structured_output_schema"] = arguments["structured_output_schema"]

    result = invocation.invoke(**arguments)
    if stream:
        assert isinstance(result, Generator)
        assert not recorded.requests
        assert list(result) == [response_type(**llm_response)]
    else:
        assert isinstance(result, LLMResult)
        assert result.message == AssistantPromptMessage(
            content="你好",
            tool_calls=llm_response["delta"]["message"]["tool_calls"],
            opaque_body=llm_response["delta"]["message"]["opaque_body"],
        )
        assert result.usage == LLMUsage(**llm_response["delta"]["usage"])
        assert result.model == "requested-model"
        assert result.system_fingerprint is None
        if isinstance(result, LLMResultWithStructuredOutput):
            assert result.structured_output is None

    assert recorded.requests == [(invoke_type, response_type, expected)]
    assert recorded.closed
    if dict_config:
        assert config == configuration


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("together", [False, True])
@pytest.mark.parametrize("zero_usage", [False, True])
def test_llm_collects_complete_calls_and_keeps_terminal_usage(
    record_invocation: RecordInvocation,
    llm_response: dict,
    structured: bool,
    together: bool,
    zero_usage: bool,
) -> None:
    invocation = LLMStructuredOutputInvocation() if structured else LLMInvocation()
    earlier_call = {
        "id": "call-0",
        "type": "function",
        "function": {
            "name": "search",
            "arguments": (
                r'{"query":"\u6587\u6863", "amount":1e+3, "id":9007199254740993}'
            ),
        },
    }
    expected_calls = [earlier_call, llm_response["delta"]["message"]["tool_calls"][0]]
    first = {
        "model": "model",
        "delta": {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "first ",
                "tool_calls": [] if together else [earlier_call],
            },
            "usage": {
                **llm_response["delta"]["usage"],
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "total_tokens": 3,
                "total_price": "0.001",
            },
        },
    }
    terminal = deepcopy(llm_response)
    terminal["delta"]["message"]["content"] = "last"
    if together:
        terminal["delta"]["message"]["tool_calls"] = expected_calls
    if zero_usage:
        terminal["delta"]["usage"] = LLMUsage.empty_usage().model_dump(mode="json")
    terminal["structured_output"] = {"answer": "first last"}
    recorded = record_invocation(
        invocation,
        [
            first,
            terminal,
            {
                "model": "model",
                "delta": {
                    "index": 0,
                    "message": {"role": "assistant", "content": None},
                },
                "structured_output": {},
            },
        ],
    )
    arguments = {
        "model_config": {"provider": "provider", "model": "model", "mode": "chat"},
        "prompt_messages": [],
        "stream": False,
    }
    if structured:
        arguments["structured_output_schema"] = {"type": "object"}

    result = invocation.invoke(**arguments)

    assert isinstance(result, LLMResult)
    assert result.message.content == "first last"
    assert result.usage == LLMUsage(**terminal["delta"]["usage"])
    assert [call.model_dump() for call in result.message.tool_calls] == expected_calls
    assert recorded.requests[0][2]["tools"] is None
    assert recorded.requests[0][2]["stop"] is None
    assert recorded.closed
    if isinstance(result, LLMResultWithStructuredOutput):
        assert result.structured_output == {"answer": "first last"}


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "chunk_order",
    [
        "multimodal",
        "text-image",
        "image-text",
        "lists",
        "text-blocks",
        "terminal-none",
        "terminal-empty",
    ],
)
def test_llm_preserves_content_order_for_each_stream_mode(
    record_invocation: RecordInvocation,
    structured: bool,
    stream: bool,
    chunk_order: str,
) -> None:
    image = {
        "type": "image",
        "format": "png",
        "mime_type": "image/png",
        "base64_data": "AP+A",
        "detail": "high",
    }
    text = {"type": "text", "data": "Here is the image"}
    if chunk_order == "multimodal":
        contents, expected = [[text, image]], [text, image]
    elif chunk_order == "text-image":
        contents, expected = [text["data"], [image]], [text, image]
    elif chunk_order == "image-text":
        contents, expected = [[image], text["data"]], [image, text]
    elif chunk_order == "lists":
        contents, expected = [[text], [image]], [text, image]
    elif chunk_order == "text-blocks":
        continuation = {"type": "text", "data": "<think>hidden</think>answer"}
        contents, expected = [[text], [continuation]], [text, continuation]
    else:
        terminal_content = None if chunk_order == "terminal-none" else ""
        contents, expected = [[text, image], terminal_content], [text, image]
    invocation = LLMStructuredOutputInvocation() if structured else LLMInvocation()
    recorded = record_invocation(
        invocation,
        [
            {
                "model": "model",
                "delta": {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                },
            }
            for content in contents
        ],
    )
    arguments = {
        "model_config": {"provider": "provider", "model": "model", "mode": "chat"},
        "prompt_messages": [],
        "stream": stream,
    }
    if structured:
        arguments["structured_output_schema"] = {"type": "object"}

    result = invocation.invoke(**arguments)

    if stream:
        assert [chunk.delta.message.content for chunk in result] == [
            AssistantPromptMessage(content=content).content for content in contents
        ]
    else:
        assert (
            result.message.content == AssistantPromptMessage(content=expected).content
        )
    assert recorded.closed


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("stream", [False, True])
def test_llm_failure_does_not_become_a_partial_success(
    record_invocation: RecordInvocation, structured: bool, stream: bool
) -> None:
    invocation = LLMStructuredOutputInvocation() if structured else LLMInvocation()
    error = RuntimeError("model unavailable")
    recorded = record_invocation(invocation, [error])
    arguments = {
        "model_config": {"provider": "provider", "model": "model", "mode": "chat"},
        "prompt_messages": [],
        "stream": stream,
    }
    if structured:
        arguments["structured_output_schema"] = {"type": "object"}

    def invoke() -> None:
        result = invocation.invoke(**arguments)
        if isinstance(result, Generator):
            list(result)

    with pytest.raises(RuntimeError) as caught:
        invoke()
    assert caught.value is error
    assert recorded.closed


@pytest.mark.parametrize(
    "invocation_type", [LLMInvocation, LLMStructuredOutputInvocation]
)
def test_llm_validates_configuration_before_invoking(
    record_invocation: RecordInvocation,
    invocation_type: type[LLMInvocation | LLMStructuredOutputInvocation],
) -> None:
    invocation = invocation_type()
    recorded = record_invocation(invocation, [])
    arguments = {
        "model_config": {"model": "missing-provider-and-mode"},
        "prompt_messages": [],
    }
    if isinstance(invocation, LLMStructuredOutputInvocation):
        arguments["structured_output_schema"] = {"type": "object"}

    with pytest.raises(ValidationError):
        invocation.invoke(**arguments)
    assert not recorded.requests


@pytest.mark.parametrize("length", [3, 4, 5])
def test_summary_threshold_controls_the_remote_call(
    record_invocation: RecordInvocation, length: int
) -> None:
    invocation = SummaryInvocation()
    recorded = record_invocation(invocation, [{"summary": "summary"}])
    text = "文" * length

    result = invocation.invoke(text, "Summarize", min_summarize_length=4)

    if length < 4:
        assert result == text
        assert not recorded.requests
    else:
        assert result == "summary"
        assert recorded.requests[0][0] == InvokeType.SYSTEM_SUMMARY
        assert recorded.requests[0][2] == {"text": text, "instruction": "Summarize"}
        assert recorded.closed


def test_summary_rejects_an_empty_response(record_invocation: RecordInvocation) -> None:
    invocation = SummaryInvocation()
    record_invocation(invocation, [])
    with pytest.raises(Exception, match="No response from summary"):
        invocation.invoke("text", "Summarize", min_summarize_length=0)


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("mixed_content", [False, True])
@pytest.mark.parametrize(
    "snapshot",
    [
        {},
        [],
        "",
        0,
        False,
        {"parts": [{"signature": "opaque", "id": 9007199254740993}]},
    ],
    ids=["object", "array", "string", "integer", "boolean", "nested-large-integer"],
)
def test_llm_replays_last_snapshot_and_content_blocks_over_http(
    session: Session,
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    structured: bool,
    stream: bool,
    mixed_content: bool,
    snapshot: JsonValue,
) -> None:
    invocation = (
        session.model.llm_structured_output if structured else session.model.llm
    )
    monkeypatch.setattr(invocation, "_generate_backwards_request_id", lambda: "opaque")
    session.install_method = InstallMethod.Serverless
    original = deepcopy(snapshot)
    content_part = TextPromptMessageContent(data="", opaque_body=snapshot)
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "lookup", "arguments": "{}"},
    }

    def response_bytes(messages: list[dict]) -> bytes:
        frames = [
            {
                "session_id": session.session_id,
                "event": "backwards_response",
                "data": {
                    "backwards_request_id": "opaque",
                    "event": "response",
                    "message": "",
                    "data": {
                        "model": "model",
                        "delta": {"index": index, "message": message},
                        "structured_output": {"answer": True} if index == 1 else None,
                    },
                },
            }
            for index, message in enumerate(messages)
        ]
        frames.append({
            "session_id": session.session_id,
            "event": "backwards_response",
            "data": {
                "backwards_request_id": "opaque",
                "event": "end",
                "message": "",
                "data": None,
            },
        })
        return "".join(json.dumps(frame) + "\n\n" for frame in frames).encode()

    server = http_server([
        Response(
            body=response_bytes([
                {"role": "assistant", "content": "first", "opaque_body": {"old": 1}},
                {
                    "role": "assistant",
                    "content": [content_part.model_dump(mode="json")]
                    if mixed_content
                    else "",
                    "opaque_body": snapshot,
                    "tool_calls": [tool_call],
                },
                {"role": "assistant", "content": "tail" if mixed_content else ""},
                {"role": "assistant", "content": None, "opaque_body": None},
            ])
        ),
        Response(body=response_bytes([{"role": "assistant", "content": "next"}])),
    ])
    session.dify_plugin_daemon_url = server.url
    arguments = {
        "model_config": {"provider": "provider", "model": "model", "mode": "chat"},
        "stream": stream,
    }
    if structured:
        arguments["structured_output_schema"] = {"type": "object"}

    first = invocation.invoke(
        **arguments, prompt_messages=[UserPromptMessage(content="first")]
    )
    if isinstance(first, LLMResult):
        message = first.message
        expected_content = (
            [
                TextPromptMessageContent(data="first"),
                content_part,
                TextPromptMessageContent(data="tail"),
            ]
            if mixed_content
            else "first"
        )
        if structured:
            assert isinstance(first, LLMResultWithStructuredOutput)
            assert first.structured_output == {"answer": True}
    else:
        chunks = list(first)
        assert [chunk.delta.message.opaque_body for chunk in chunks] == [
            {"old": 1},
            original,
            None,
            None,
        ]
        assert [chunk.delta.message.content for chunk in chunks] == [
            "first",
            [content_part] if mixed_content else "",
            "tail" if mixed_content else "",
            None,
        ]
        message = chunks[1].delta.message
        expected_content = [content_part] if mixed_content else ""

    assert message.content == expected_content
    assert message.opaque_body == original
    assert type(message.opaque_body) is type(original)
    assert [call.model_dump() for call in message.tool_calls] == [tool_call]
    if mixed_content:
        assert isinstance(message.content, list)
        block = message.content[0 if stream else 1]
        assert block.opaque_body == original
        assert type(block.opaque_body) is type(original)

    following = invocation.invoke(
        **arguments,
        prompt_messages=[message, UserPromptMessage(content="next")],
    )
    if isinstance(following, LLMResult):
        next_message = following.message
        if structured:
            assert isinstance(following, LLMResultWithStructuredOutput)
            assert following.structured_output is None
    else:
        following_chunks = list(following)
        assert len(following_chunks) == 1
        next_message = following_chunks[0].delta.message

    assert next_message.content == "next"
    assert next_message.opaque_body is None
    assert next_message.tool_calls == []
    assert len(server.requests) == 2
    request = json.loads(server.requests[1].body)["data"]["data"]
    assert request["type"] == (
        InvokeType.LLMStructuredOutput.value if structured else InvokeType.LLM.value
    )
    replayed = request["request"]["prompt_messages"][0]
    assert replayed == message.model_dump(mode="json")
    assert type(replayed["opaque_body"]) is type(original)
    assert snapshot == original
