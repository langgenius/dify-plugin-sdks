import json
from collections import UserDict
from collections.abc import Mapping
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import gevent.socket
import pytest
from gevent.threadpool import ThreadPool

from dify_plugin.entities.model.llm import LLMResultChunk
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
from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model import ai_model
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


class DuckJsonObject:
    def __init__(self) -> None:
        self.trace: list[str] = []

    def get(self, key: str, default: object = None) -> str:
        del key, default
        self.trace.append("get")
        return "chat.completion"

    def __contains__(self, key: object) -> bool:
        del key
        self.trace.append("contains")
        return True

    def __getitem__(self, key: str) -> str:
        del key
        self.trace.append("getitem")
        return "chat.completion"


class StatefulTruth:
    def __init__(self) -> None:
        self.calls = 0

    def __bool__(self) -> bool:
        self.calls += 1
        return self.calls == 1


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
def test_generate_preserves_unsupported_non_user_content_until_json_encoding(
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
    converted = llm._convert_prompt_message_to_dict(message, credentials)
    assert converted["content"][-1] is unsupported

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post"
        ) as post,
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.json.dumps",
            wraps=json.dumps,
        ) as dumps,
        pytest.raises(
            TypeError, match=f"{content_type.__name__} is not JSON serializable"
        ),
    ):
        llm._generate("model", credentials, [message], {}, stream=False)

    dumps.assert_called_once()
    post.assert_not_called()
    assert message.content == content


@pytest.mark.parametrize(
    "content_type", [AudioPromptMessageContent, DocumentPromptMessageContent]
)
def test_provider_override_can_serialize_unsupported_content_after_super(
    content_type: type[AudioPromptMessageContent | DocumentPromptMessageContent],
) -> None:
    class MediaUrlModel(OAICompatLargeLanguageModel):
        def _convert_prompt_message_to_dict(
            self, message: PromptMessage, credentials: dict | None = None
        ) -> dict:
            converted = super()._convert_prompt_message_to_dict(message, credentials)
            converted["content"] = converted["content"][0].data
            return converted

    content = content_type(
        format="bin",
        mime_type="application/octet-stream",
        url="https://example.com/file",
    )
    llm = MediaUrlModel([])
    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=MagicMock(status_code=HTTPStatus.OK),
        ) as post,
        patch.object(llm, "_handle_generate_response"),
    ):
        llm._generate(
            "model",
            {"endpoint_url": "https://example.com/v1", "mode": "chat"},
            [SystemPromptMessage(content=[content])],
            {},
            stream=False,
        )

    assert json.loads(post.call_args.kwargs["data"])["messages"] == [
        {"role": "system", "content": content.data}
    ]


@pytest.mark.parametrize(
    "message_type", [SystemPromptMessage, AssistantPromptMessage, ToolPromptMessage]
)
def test_num_tokens_counts_non_user_text_without_counting_media(
    message_type: type[PromptMessage],
) -> None:
    message = message_type.model_validate({
        "content": [
            TextPromptMessageContent(data="first"),
            ImagePromptMessageContent(
                format="png", mime_type="image/png", url="https://example.com/image.png"
            ),
            TextPromptMessageContent(data="second"),
            AudioPromptMessageContent(
                format="mp3",
                mime_type="audio/mpeg",
                url="https://example.com/audio.mp3",
            ),
            DocumentPromptMessageContent(
                format="pdf",
                mime_type="application/pdf",
                url="https://example.com/doc.pdf",
            ),
        ],
        "tool_call_id": "call-1",
    })
    llm = OAICompatLargeLanguageModel([])
    with patch.object(llm, "_get_num_tokens_by_gpt2", side_effect=len) as tokenize:
        count = llm._num_tokens_from_messages(
            [message], credentials={"function_calling_type": "tool_call"}
        )

    expected = [message.role.value, "firstsecond"]
    if isinstance(message, ToolPromptMessage):
        expected.append("call-1")
    assert [call.args[0] for call in tokenize.call_args_list] == expected
    assert count == 6 + sum(map(len, expected))


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
        count = OAICompatLargeLanguageModel([]).get_num_tokens(
            "model", {"function_calling_type": "tool_call"}, messages
        )
    finally:
        pool.kill()

    # GPT2 counts the literal spelling as ordinary text, not a control token.
    assert count == 55


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


def test_validate_credentials_wraps_unreadable_error_response() -> None:
    error = RuntimeError("broken body")
    response = MagicMock(status_code=HTTPStatus.BAD_REQUEST)
    type(response).text = PropertyMock(side_effect=error)
    response.close.side_effect = RuntimeError("close failed")
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": "use",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is error
    response.close.assert_called_once()


def test_validate_credentials_accepts_mapping_response() -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = UserDict({"object": "chat.completion"})
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)


def test_validate_credentials_wraps_lazy_mapping_errors() -> None:
    error_message = "lazy response failed"
    json_result = MagicMock(spec=Mapping)
    json_result.get.side_effect = RuntimeError(error_message)
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = json_result
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError, match=error_message),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)


def test_validate_credentials_preserves_prepared_credential_errors() -> None:
    sentinel = CredentialsValidateFailedError("prepared credentials failed")
    credentials = MagicMock()
    credentials.get.side_effect = sentinel

    with pytest.raises(CredentialsValidateFailedError) as exc_info:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_response_credential_errors() -> None:
    sentinel = CredentialsValidateFailedError("response failed")
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_mapping_membership_access() -> None:
    json_result = DuckJsonObject()
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = json_result
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert json_result.trace == ["get", "contains", "getitem"]


def test_validate_credentials_compares_status_once() -> None:
    status = MagicMock()
    status.__ne__.side_effect = [True, False]
    response = MagicMock(status_code=status, text="failed")
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": "use",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    status.__ne__.assert_called_once_with(HTTPStatus.OK)


def test_validate_credentials_preserves_failed_status_second_access() -> None:
    sentinel = CredentialsValidateFailedError("second status read failed")
    response = MagicMock(text="failed")
    type(response).status_code = PropertyMock(
        side_effect=[HTTPStatus.BAD_REQUEST, sentinel],
    )
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_response_truthiness_hook() -> None:
    sentinel = CredentialsValidateFailedError("response truthiness failed")
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = RuntimeError("json failed")
    response.__bool__.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_status_failure_truthiness_hook() -> None:
    sentinel = CredentialsValidateFailedError("response truthiness failed")
    response = MagicMock(text="failed")
    type(response).status_code = PropertyMock(
        side_effect=[HTTPStatus.BAD_REQUEST, RuntimeError("status failed")],
    )
    response.__bool__.side_effect = sentinel
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert exc_info.value is sentinel


def test_validate_credentials_truth_tests_stream_mode_once() -> None:
    stream_result = StatefulTruth()
    stream_mode = MagicMock()
    stream_mode.__eq__.return_value = stream_result
    response = MagicMock(status_code=HTTPStatus.OK)
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": stream_mode,
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert stream_result.calls == 1
    assert post.call_args.kwargs["stream"] is True
    response.json.assert_not_called()


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
        (
            [
                _stream_choice({"reasoning_content": "A"}),
                "data: not-json",
            ],
            "<think>\nA\n</think>",
            "Non-JSON encountered.",
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
            # finish_reason is reset by trailing heartbeat deltas that
            # carry ``"finish_reason": null``; this is a pre-existing
            # quirk in the stream handler and is not what this fix
            # targets.
            None,
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
    response = MagicMock()
    response.iter_lines.return_value = lines
    llm = OAICompatLargeLanguageModel([])
    final_chunk = object()

    with patch.object(
        llm,
        "_create_final_llm_result_chunk",
        return_value=final_chunk,
    ) as create_final:
        results = list(
            llm._handle_generate_stream_response(
                model="model",
                credentials={},
                response=response,
                prompt_messages=[],
            )
        )

    stream_chunks = [result for result in results if isinstance(result, LLMResultChunk)]
    assert "".join(chunk.delta.message.content for chunk in stream_chunks) == (
        expected_content
    )
    assert [chunk.delta.index for chunk in stream_chunks] == sorted(
        chunk.delta.index for chunk in stream_chunks
    )
    assert results[-1] is final_chunk
    create_final.assert_called_once()
    assert create_final.call_args.kwargs["full_content"] == expected_content
    assert create_final.call_args.kwargs["finish_reason"] == expected_finish_reason
    assert create_final.call_args.kwargs["usage"] == expected_usage
    assert create_final.call_args.kwargs["index"] > stream_chunks[-1].delta.index
