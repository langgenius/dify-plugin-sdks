import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from functools import partial

import pytest
from pydantic import JsonValue

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultWithStructuredOutput,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    TextPromptMessageContent,
    UserPromptMessage,
)

# Import HTTP after the SDK applies its gevent patch.
# isort: split

import httpx


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("mixed_content", [True, False])
@pytest.mark.parametrize("structured_output", [True, False])
@pytest.mark.parametrize(
    "opaque_body",
    [
        {"blocks": [{"signature": "signed", "id": 9007199254740993}]},
        {},
        [],
        "",
        0,
        False,
    ],
)
def test_llm_invocation_preserves_last_snapshot_and_resets_between_calls(
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
    mixed_content: bool,
    structured_output: bool,
    opaque_body: JsonValue,
) -> None:
    requests = []
    content_part = TextPromptMessageContent(data="", opaque_body=opaque_body)
    tool_call = AssistantPromptMessage.ToolCall(
        id="call-1",
        type="function",
        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="lookup", arguments="{}"
        ),
    )
    usage = LLMUsage.empty_usage().model_copy(
        update={
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "prompt_price": Decimal("0.1"),
            "completion_price": Decimal("0.2"),
            "total_price": Decimal("0.3"),
            "currency": "CNY",
            "latency": 0.5,
        }
    )

    def respond(request: httpx.Request) -> httpx.Response:
        invocation = json.loads(request.content)["data"]["data"]
        requests.append(invocation["request"])
        messages = (
            [
                {"content": "answer", "opaque_body": {"partial": True}},
                {
                    "content": [content_part.model_dump(mode="json")]
                    if mixed_content
                    else "",
                    "opaque_body": opaque_body,
                    "tool_calls": [tool_call.model_dump(mode="json")],
                },
                {"content": "tail" if mixed_content else ""},
                {"content": ""},
            ]
            if len(requests) == 1
            else [{"content": "next answer"}]
        )
        events = [
            {
                "session_id": "test",
                "event": "backwards_response",
                "data": {
                    "backwards_request_id": invocation["backwards_request_id"],
                    "event": "response",
                    "message": "",
                    "data": {
                        "model": "test-model",
                        "delta": {
                            "index": index,
                            "message": message,
                            "usage": usage.model_dump(mode="json")
                            if index < 2
                            else None,
                        },
                        "structured_output": {"answer": True} if index == 1 else None,
                    },
                },
            }
            for index, message in enumerate(messages)
        ]
        return httpx.Response(200, text="\n".join(map(json.dumps, events)))

    client_type = httpx.Client
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        "dify_plugin.core.runtime.httpx.Client",
        lambda: client_type(transport=transport),
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        session = Session(
            session_id="test",
            executor=executor,
            reader=StdioRequestReader(),
            writer=StdioResponseWriter(),
            dify_plugin_daemon_url="http://daemon.test",
        )
        config = LLMModelConfig(provider="test", model="test-model", mode="chat")
        invoke = (
            partial(
                session.model.llm_structured_output.invoke,
                structured_output_schema={"type": "object"},
            )
            if structured_output
            else session.model.llm.invoke
        )
        first = invoke(
            model_config=config,
            prompt_messages=[UserPromptMessage(content="hello")],
            stream=stream,
        )
        if isinstance(first, LLMResult):
            message = first.message
            assert message.tool_calls == [tool_call]
            assert first.usage == usage.model_copy(
                update={"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6}
            )
            if structured_output:
                assert isinstance(first, LLMResultWithStructuredOutput)
                assert first.structured_output == {"answer": True}
            assert message.content == (
                [
                    TextPromptMessageContent(data="answer"),
                    content_part,
                    TextPromptMessageContent(data="tail"),
                ]
                if mixed_content
                else "answer"
            )
            if mixed_content:
                assert isinstance(message.content, list)
                assert message.content[1].opaque_body == opaque_body
                assert type(message.content[1].opaque_body) is type(opaque_body)
        else:
            chunks = list(first)
            message = chunks[1].delta.message
            assert chunks[-1].delta.message.opaque_body is None
            if mixed_content:
                assert [chunk.delta.message.content for chunk in chunks] == [
                    "answer",
                    [content_part],
                    "tail",
                    "",
                ]
                assert isinstance(message.content, list)
                assert message.content[0].opaque_body == opaque_body
                assert type(message.content[0].opaque_body) is type(opaque_body)

        assert message.opaque_body == opaque_body
        assert type(message.opaque_body) is type(opaque_body)
        second = invoke(
            model_config=config,
            prompt_messages=[message],
            stream=stream,
        )
        if isinstance(second, LLMResult):
            second_message = second.message
        else:
            second_chunks = list(second)
            second_message = second_chunks[0].delta.message
        assert second_message.opaque_body is None
        assert requests[1]["prompt_messages"][0]["opaque_body"] == opaque_body


@pytest.mark.parametrize("opaque_body", [{}, [], "", 0, False, {"signature": "s"}])
def test_assistant_with_opaque_body_is_not_empty(opaque_body: JsonValue) -> None:
    assert not AssistantPromptMessage(opaque_body=opaque_body).is_empty()


def test_assistant_tool_call_is_not_empty() -> None:
    message = AssistantPromptMessage.model_validate({
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": "{}"},
            },
        ],
    })

    assert not message.is_empty()
    assert AssistantPromptMessage().is_empty()
