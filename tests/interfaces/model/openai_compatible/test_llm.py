import json
from http import HTTPStatus
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import gevent.socket
import pytest
import requests
from gevent.threadpool import ThreadPool

from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    AudioPromptMessageContent,
    DocumentPromptMessageContent,
    ImagePromptMessageContent,
    PromptMessage,
    SystemPromptMessage,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
    VideoPromptMessageContent,
)
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.interfaces.model import ai_model
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


def _stream_choice(delta: dict, finish_reason: str | None = None) -> str:
    return "data: " + json.dumps({
        "choices": [{"delta": delta, "finish_reason": finish_reason}]
    })


@pytest.mark.parametrize(
    ("stream_mode_auth", "stream", "max_tokens"),
    [("not_use", False, 5), ("use", True, 10)],
)
def test_validate_credentials_passes_extra_headers(
    stream_mode_auth: str,
    stream: bool,
    max_tokens: int,
) -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = {"object": "chat.completion"}
    response.close.side_effect = RuntimeError("close failed")
    api_key = str(123)
    credentials = {
        "api_key": api_key,
        "endpoint_url": "https://example.com/v1",
        "extra_headers": {
            "Authorization": str(456),
            "Content-Type": "application/custom+json",
            "X-Api-Key": str(789),
        },
        "mode": "chat",
        "stream_mode_auth": stream_mode_auth,
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert post.call_args.kwargs["headers"] == {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/custom+json",
        "X-Api-Key": str(789),
    }
    assert post.call_args.kwargs.get("stream", False) is stream
    assert post.call_args.kwargs["json"]["max_tokens"] == max_tokens
    response.close.assert_called_once()


@pytest.mark.parametrize(
    ("video_kwargs", "expected_url"),
    [
        (
            {"url": "https://example.com/video.mp4"},
            "https://example.com/video.mp4",
        ),
        ({"base64_data": "AAAA"}, "data:video/mp4;base64,AAAA"),
    ],
)
def test_convert_prompt_message_to_dict_serializes_video(
    video_kwargs: dict[str, str],
    expected_url: str,
) -> None:
    video = VideoPromptMessageContent(
        format="mp4",
        mime_type="video/mp4",
        **video_kwargs,
    )

    result = OAICompatLargeLanguageModel([])._convert_prompt_message_to_dict(
        UserPromptMessage(
            content=[
                TextPromptMessageContent(data="Describe the video"),
                video,
            ]
        )
    )

    assert result == {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe the video"},
            {
                "type": "video_url",
                "video_url": {"url": expected_url},
            },
        ],
    }


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("function_calling_type", ["tool_call", "function_call"])
@pytest.mark.parametrize(
    ("image_kwargs", "expected_url"),
    [
        ({"url": "https://example.com/image.png"}, "https://example.com/image.png"),
        ({"base64_data": "AAAA"}, "data:image/png;base64,AAAA"),
    ],
)
def test_generate_serializes_images_in_all_message_roles(
    image_kwargs: dict[str, str],
    expected_url: str,
    function_calling_type: str,
    stream: bool,
) -> None:
    content = [
        ImagePromptMessageContent(
            format="png", mime_type="image/png", detail="high", **image_kwargs
        ),
        TextPromptMessageContent(data="Describe this image."),
    ]
    tool_call = AssistantPromptMessage.ToolCall(
        id="call-1",
        type="function",
        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
            name="describe", arguments="{}"
        ),
    )
    messages = [
        UserPromptMessage(content=content, name="user-name"),
        SystemPromptMessage(content=content, name="system-name"),
        AssistantPromptMessage(
            content=content, name="assistant-name", tool_calls=[tool_call]
        ),
        ToolPromptMessage(content=content, tool_call_id="call-1"),
    ]
    llm = OAICompatLargeLanguageModel([])
    response = MagicMock(status_code=HTTPStatus.OK)
    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ) as post,
        patch.object(llm, "_handle_generate_response"),
        patch.object(llm, "_handle_generate_stream_response"),
    ):
        llm._generate(
            "model",
            {
                "endpoint_url": "https://example.com/v1",
                "mode": "chat",
                "function_calling_type": function_calling_type,
            },
            messages,
            {},
            stream=stream,
        )

    expected_content = [
        {
            "type": "image_url",
            "image_url": {"url": expected_url, "detail": "high"},
        },
        {"type": "text", "text": "Describe this image."},
    ]
    assistant_metadata = (
        {"tool_calls": [tool_call.model_dump()]}
        if function_calling_type == "tool_call"
        else {"function_call": {"name": "describe", "arguments": "{}"}}
    )
    tool_metadata = (
        {"role": "tool", "tool_call_id": "call-1"}
        if function_calling_type == "tool_call"
        else {"role": "function", "name": "call-1"}
    )
    request = post.call_args.kwargs
    assert request["stream"] is stream
    assert json.loads(request["data"]) == {
        "model": "model",
        "stream": stream,
        "messages": [
            {"role": "user", "content": expected_content, "name": "user-name"},
            {"role": "system", "content": expected_content, "name": "system-name"},
            {
                "role": "assistant",
                "content": expected_content,
                "name": "assistant-name",
                **assistant_metadata,
            },
            {"content": expected_content, **tool_metadata},
        ],
    }
    assert messages[0].content == content


def test_convert_prompt_messages_preserves_text_and_empty_content() -> None:
    llm = OAICompatLargeLanguageModel([])
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "describe", "arguments": "{}"},
    }
    messages = [
        UserPromptMessage(content="plain text"),
        UserPromptMessage(content=None),
        UserPromptMessage(content=[]),
        SystemPromptMessage(content="instruction"),
        SystemPromptMessage(content=None),
        AssistantPromptMessage(content=None),
        AssistantPromptMessage(content=[]),
        AssistantPromptMessage.model_validate({"tool_calls": [tool_call]}),
        ToolPromptMessage(content="result", tool_call_id="call-1", name="ignored"),
    ]
    assert [
        llm._convert_prompt_message_to_dict(m, {"function_calling_type": "tool_call"})
        for m in messages
    ] == [
        {"role": "user", "content": "plain text"},
        {"role": "user", "content": []},
        {"role": "user", "content": []},
        {"role": "system", "content": "instruction"},
        {"role": "system", "content": None},
        {"role": "assistant", "content": None},
        {"role": "assistant", "content": []},
        {"role": "assistant", "content": None, "tool_calls": [tool_call]},
        {"role": "tool", "content": "result", "tool_call_id": "call-1"},
    ]


@pytest.mark.parametrize(
    "message_type", [SystemPromptMessage, AssistantPromptMessage, ToolPromptMessage]
)
@pytest.mark.parametrize(
    "content_type", [AudioPromptMessageContent, DocumentPromptMessageContent]
)
@pytest.mark.parametrize("mixed", [False, True])
def test_unsupported_non_user_content_is_rejected_before_sending_request(
    message_type: type[PromptMessage],
    content_type: type[AudioPromptMessageContent | DocumentPromptMessageContent],
    mixed: bool,
) -> None:
    unsupported = content_type(
        format="bin",
        mime_type="application/octet-stream",
        url="https://example.com/file",
    )
    content = (
        [
            TextPromptMessageContent(data="Describe the inputs."),
            ImagePromptMessageContent(
                format="png", mime_type="image/png", url="https://example.com/image.png"
            ),
            unsupported,
        ]
        if mixed
        else [unsupported]
    )
    message = message_type.model_validate({
        "content": content,
        "tool_call_id": "call-1",
    })
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "function_calling_type": "tool_call",
    }
    llm = OAICompatLargeLanguageModel([])

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post"
        ) as post,
        pytest.raises(InvokeError),
    ):
        list(llm.invoke("model", credentials, [message], {}, stream=False))

    post.assert_not_called()


@pytest.mark.parametrize(
    "message_type", [SystemPromptMessage, AssistantPromptMessage, ToolPromptMessage]
)
def test_num_tokens_counts_non_user_text_parts_like_plain_text(
    message_type: type[PromptMessage],
) -> None:
    message = message_type.model_validate({
        "content": [
            TextPromptMessageContent(data="first"),
            TextPromptMessageContent(data="second"),
        ],
        "tool_call_id": "call-1",
    })
    llm = OAICompatLargeLanguageModel([])
    credentials = {"function_calling_type": "tool_call"}
    count = llm.get_num_tokens("model", credentials, [message])
    text_only = message.model_copy(update={"content": "firstsecond"})
    empty = message.model_copy(update={"content": ""})

    assert count == llm.get_num_tokens("model", credentials, [text_only])
    assert count > llm.get_num_tokens("model", credentials, [empty])


@pytest.mark.parametrize("use_threadpool", [False, True])
def test_num_tokens_treats_special_token_spelling_as_text(
    use_threadpool: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_model,
        "socket",
        SimpleNamespace(socket=gevent.socket.socket if use_threadpool else None),
    )
    pool = ThreadPool(1)
    monkeypatch.setattr(ai_model, "threadpool", pool, raising=False)
    content = [TextPromptMessageContent(data="Explain the <|endoftext|> token.")]
    messages = [
        SystemPromptMessage(content=content),
        AssistantPromptMessage(content=content),
        ToolPromptMessage(content=content, tool_call_id="call-1"),
    ]
    try:
        model = OAICompatLargeLanguageModel([])
        credentials = {"function_calling_type": "tool_call"}
        count = model.get_num_tokens("model", credentials, messages)
        empty = [message.model_copy(update={"content": ""}) for message in messages]
        assert count > model.get_num_tokens("model", credentials, empty)
    finally:
        pool.kill()


def test_generate_encodes_request_json_as_utf8() -> None:
    content = "你好😀\ud800"
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "extra_headers": {"Content-Type": "application/custom+json"},
        "mode": "chat",
    }
    response = MagicMock(status_code=HTTPStatus.OK, encoding=None)
    llm = OAICompatLargeLanguageModel([])

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        llm._generate(
            "model",
            credentials,
            [UserPromptMessage(content=content)],
            {},
        )

    request = post.call_args.kwargs
    assert "json" not in request
    assert "你好😀".encode() in request["data"]
    assert b"\\ud800" in request["data"]
    assert json.loads(request["data"])["messages"][0]["content"] == content
    assert request["headers"]["Content-Type"] == "application/custom+json"

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        ) as invalid_post,
        pytest.raises(
            ValueError,
            match="Out of range float values are not JSON compliant",
        ),
    ):
        llm._generate(
            "model",
            credentials,
            [UserPromptMessage(content="test")],
            {"temperature": float("nan")},
        )

    invalid_post.assert_not_called()


@pytest.mark.parametrize("extra_headers", [False, "", [], [("X-Api-Key", "value")]])
def test_validate_credentials_rejects_non_mapping_extra_headers(
    extra_headers: object,
) -> None:
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "extra_headers": extra_headers,
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        ) as post,
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    post.assert_not_called()


@pytest.mark.parametrize(
    ("lines", "expected_content", "expected_finish_reason", "expected_usage"),
    [
        (
            [
                _stream_choice({"reasoning_content": "A"}),
                _stream_choice({"reasoning_content": ""}, "stop"),
                (
                    'data: {"choices":[],"usage":'
                    '{"prompt_tokens":1,"completion_tokens":1}}'
                ),
                "data: [DONE]",
            ],
            "<think>\nA\n</think>",
            "stop",
            {"prompt_tokens": 1, "completion_tokens": 1},
        ),
        (
            [
                _stream_choice({"reasoning_content": "A"}, "stop"),
                _stream_choice({"reasoning_content": ""}, "stop"),
                _stream_choice({"reasoning": "B"}, "stop"),
                _stream_choice({"reasoning": ""}, "stop"),
                _stream_choice(
                    {"reasoning_content": "", "reasoning": ""},
                    "stop",
                ),
                _stream_choice({"reasoning_content": "C"}, "stop"),
                _stream_choice(
                    {"reasoning_content": "", "content": "Answer"},
                    "stop",
                ),
                "data: [DONE]",
            ],
            "<think>\nABC\n</think>Answer",
            "stop",
            None,
        ),
        # When intermediate deltas are absent or empty (the MTPLX
        # Qwen3 / heartbeat pattern), reasoning across them must be
        # merged into a single ``<think>`` block instead of being
        # split by premature ``</think>`` markers. Tool/function call
        # boundaries still legitimately close the block; a final empty
        # close is emitted once at stream end.
        (
            [
                _stream_choice({"reasoning_content": "A"}),
                _stream_choice({"reasoning_content": None}),
                _stream_choice({"reasoning_content": "B"}),
                _stream_choice({}),
                _stream_choice({"reasoning_content": "C"}),
                _stream_choice({
                    "reasoning_content": "",
                    "tool_calls": [{"id": "call"}],
                }),
                _stream_choice({"reasoning_content": "D"}),
                _stream_choice({
                    "reasoning_content": "",
                    "function_call": {"name": "call"},
                }),
                _stream_choice({"reasoning_content": "E"}),
                "data: [DONE]",
            ],
            "<think>\nABC\n</think><think>\nD\n</think><think>\nE\n</think>",
            None,
            None,
        ),
        # MTPLX / Qwen3 streaming pattern (issue #277 follow-up):
        # the runtime inserts heartbeat deltas with no reasoning_content
        # key at all mid-reasoning. The bypass must treat those the
        # same as present-but-empty reasoning chunks and skip them,
        # otherwise the think block gets fragmented into many entries.
        (
            [
                _stream_choice({"reasoning_content": "He"}),
                _stream_choice({}, finish_reason=None),
                _stream_choice({"reasoning_content": "llo"}),
                _stream_choice({}, finish_reason=None),
                _stream_choice({"reasoning_content": " world"}),
                _stream_choice({}, finish_reason=None),
                _stream_choice({"content": "Final."}, "stop"),
                "data: [DONE]",
            ],
            "<think>\nHello world\n</think>Final.",
            "stop",
            None,
        ),
        # Same heartbeat pattern, but with ``reasoning`` key instead of
        # ``reasoning_content`` (some LiteLLM-style proxies do this).
        (
            [
                _stream_choice({"reasoning": "abc"}),
                _stream_choice({}, finish_reason=None),
                _stream_choice({"reasoning": "def"}),
                _stream_choice({"content": "OK"}, "stop"),
                "data: [DONE]",
            ],
            "<think>\nabcdef\n</think>OK",
            "stop",
            None,
        ),
        # Heartbeat deltas must NOT skip the close once reasoning has
        # genuinely ended (i.e. a visible content chunk arrived). The
        # post-close heartbeats are still ignored so they don't reopen
        # a second think block.
        (
            [
                _stream_choice({"reasoning_content": "X"}),
                _stream_choice({"content": "ans"}, "stop"),
                _stream_choice({}, finish_reason=None),
                _stream_choice({}, finish_reason=None),
                "data: [DONE]",
            ],
            "<think>\nX\n</think>ans",
            "stop",
            None,
        ),
    ],
)
def test_stream_reasoning_is_closed_at_end(
    lines: list[str],
    expected_content: str,
    expected_finish_reason: str | None,
    expected_usage: dict | None,
) -> None:
    response = requests.Response()
    response.encoding = "utf-8"
    response.raw = BytesIO(("\n\n".join(lines) + "\n\n").encode())
    llm = OAICompatLargeLanguageModel([])
    results = list(
        llm._handle_generate_stream_response(
            model="model",
            credentials={},
            response=response,
            prompt_messages=[],
        )
    )

    assert "".join(chunk.delta.message.content or "" for chunk in results) == (
        expected_content
    )
    assert [chunk.delta.index for chunk in results] == sorted(
        chunk.delta.index for chunk in results
    )
    terminal = results[-1].delta
    assert terminal.finish_reason == expected_finish_reason
    assert terminal.usage is not None
    if expected_usage is not None:
        assert terminal.usage.prompt_tokens == expected_usage["prompt_tokens"]
        assert terminal.usage.completion_tokens == expected_usage["completion_tokens"]
    else:
        assert terminal.usage.completion_tokens > 0
