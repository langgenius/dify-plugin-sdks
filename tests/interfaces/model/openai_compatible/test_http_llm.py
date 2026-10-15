from __future__ import annotations

import json
from collections.abc import Generator
from decimal import Decimal
from typing import TYPE_CHECKING

import gevent
import pytest
from gevent.event import Event

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ParameterRule, ParameterType
from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
    UserPromptMessage,
)
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.interfaces.model.openai_compatible import llm
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)
from tests.http_server import HTTPServerFactory, Response

if TYPE_CHECKING:
    from requests import Response as HTTPResponse

pytestmark = pytest.mark.integration


class LegacyResponseLLM(OAICompatLargeLanguageModel):
    """Use the response hooks implemented by existing official plugins."""

    def _handle_generate_response(
        self,
        model: str,
        credentials: dict,
        response: HTTPResponse,
        prompt_messages: list[PromptMessage],
    ) -> LLMResult:
        return super()._handle_generate_response(
            model, credentials, response, prompt_messages
        )

    def _handle_generate_stream_response(
        self,
        model: str,
        credentials: dict,
        response: HTTPResponse,
        prompt_messages: list[PromptMessage],
    ) -> Generator[LLMResultChunk]:
        yield from super()._handle_generate_stream_response(
            model, credentials, response, prompt_messages
        )

    def _create_final_llm_result_chunk(
        self,
        index: int,
        message: AssistantPromptMessage,
        finish_reason: str | None,
        usage: dict | None,
        model: str,
        prompt_messages: list[PromptMessage],
        credentials: dict,
        full_content: str,
    ) -> LLMResultChunk:
        return super()._create_final_llm_result_chunk(
            index,
            message,
            finish_reason,
            usage,
            model,
            prompt_messages,
            credentials,
            full_content,
        )


@pytest.fixture
def structured_model() -> OAICompatLargeLanguageModel:
    schema = OAICompatLargeLanguageModel([]).get_customizable_model_schema(
        "model", {"mode": "chat"}
    )
    # Official compatible providers expose these options through their schema.
    schema.parameter_rules.extend([
        ParameterRule(
            name="response_format",
            label=I18nObject(en_us="Response format"),
            type=ParameterType.STRING,
            options=["text", "json_object", "json_schema"],
        ),
        ParameterRule(
            name="json_schema",
            label=I18nObject(en_us="JSON schema"),
            type=ParameterType.STRING,
        ),
    ])
    return OAICompatLargeLanguageModel([schema])


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (
            {
                "response_format": "json_schema",
                "json_schema": '{"name":"answer","schema":{"type":"object"}}',
            },
            {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": {"type": "object"}},
            },
        ),
        ({"response_format": "json_object"}, {"type": "json_object"}),
        ({"response_format": "text"}, {"type": "text"}),
        ({"json_schema": "unused"}, None),
    ],
)
def test_structured_output_parameters_reach_the_provider(
    http_server: HTTPServerFactory,
    structured_model: OAICompatLargeLanguageModel,
    parameters: dict,
    expected: dict | None,
) -> None:
    server = http_server([
        Response(
            body=b'{"choices":[{"message":{"content":"{}"}}],'
            b'"usage":{"prompt_tokens":1,"completion_tokens":1}}'
        )
    ])

    chunks = list(
        structured_model.invoke(
            "model",
            {"mode": "chat", "endpoint_url": server.url},
            [UserPromptMessage(content="Answer as JSON")],
            model_parameters=parameters,
            stream=False,
        )
    )

    assert chunks[-1].delta.message.content == "{}"
    payload = json.loads(server.requests[0].body)
    assert payload.get("response_format") == expected
    assert "json_schema" not in payload


@pytest.mark.parametrize("schema", [None, "", "{broken", "[]"])
def test_invalid_structured_schema_fails_before_sending_a_request(
    http_server: HTTPServerFactory,
    structured_model: OAICompatLargeLanguageModel,
    schema: str | None,
) -> None:
    server = http_server([])
    with pytest.raises(InvokeError, match=r"[Ss]chema"):
        list(
            structured_model.invoke(
                "model",
                {"mode": "chat", "endpoint_url": server.url},
                [UserPromptMessage(content="Answer as JSON")],
                model_parameters={
                    "response_format": "json_schema",
                    "json_schema": schema,
                },
                stream=False,
            )
        )
    assert server.requests == []
    assert structured_model.started_at == 0


@pytest.mark.parametrize("mode", ["chat", "completion"])
def test_invoke_sends_json_and_reads_non_stream_response(
    http_server: HTTPServerFactory, mode: str
) -> None:
    choice = {"message": {"content": "回答"}} if mode == "chat" else {"text": "回答"}
    server = http_server([
        Response(
            body=json.dumps({
                "id": "response-1",
                "model": "upstream-model",
                "choices": [choice],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }).encode()
        )
    ])
    content = "你好😀\ud800"
    chunks = list(
        OAICompatLargeLanguageModel([]).invoke(
            model="display-model",
            credentials={
                "mode": mode,
                "endpoint_url": f"{server.url}/v1/",
                "endpoint_model_name": "request-model",
                "api_key": "test-key",
                "extra_headers": {
                    "Content-Type": "application/custom+json",
                    "X-Dify-App-Id": "app-1",
                },
            },
            prompt_messages=[UserPromptMessage(content=content)],
            model_parameters={"temperature": 0.25},
            stop=["stop"],
            user="user-1",
            stream=False,
        )
    )

    assert len(chunks) == 1
    assert chunks[0].model == "upstream-model"
    assert chunks[0].delta.message.content == "回答"
    assert chunks[0].delta.usage is not None
    assert chunks[0].delta.usage.total_tokens == 6
    request = server.requests[0]
    assert request.method == "POST"
    assert request.path == (
        "/v1/chat/completions" if mode == "chat" else "/v1/completions"
    )
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["X-Dify-App-Id"] == "app-1"
    assert request.headers["Content-Type"] == "application/custom+json"
    assert "你好😀".encode() in request.body
    assert b"\\ud800" in request.body
    payload = json.loads(request.body)
    assert payload["model"] == "request-model"
    assert payload["stream"] is False
    assert payload["temperature"] == pytest.approx(0.25)
    assert payload["stop"] == ["stop"]
    assert payload["user"] == "user-1"
    if mode == "chat":
        assert payload["messages"] == [{"role": "user", "content": content}]
    else:
        assert payload["prompt"] == content


@pytest.mark.parametrize("mode", ["chat", "completion"])
def test_non_stream_usage_keeps_existing_fallback_estimates(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    choice = (
        {"message": {"content": "Answer"}} if mode == "chat" else {"text": "Answer"}
    )
    server = http_server([Response(body=json.dumps({"choices": [choice]}).encode())])
    model = OAICompatLargeLanguageModel([])
    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", len)

    chunks = list(
        model.invoke(
            "model",
            {"mode": mode, "endpoint_url": server.url},
            [
                UserPromptMessage(content="Question"),
                AssistantPromptMessage(content="history"),
            ],
            stream=False,
        )
    )

    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.prompt_tokens == 285
    assert usage.completion_tokens == 215
    assert model.started_at == 0


@pytest.mark.parametrize("calling_type", ["tool_call", "function_call"])
@pytest.mark.parametrize("reported_usage", [True, False])
@pytest.mark.parametrize("include_content", [True, False])
def test_non_stream_tool_calls_preserve_arguments_and_request_schema(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    calling_type: str,
    reported_usage: bool,
    include_content: bool,
) -> None:
    function = {"name": "weather", "arguments": '{"city":"北京"}'}
    message = {"content": None} if include_content else {}
    if calling_type == "tool_call":
        message["tool_calls"] = [
            {"id": "call-1", "type": "function", "function": function}
        ]
    else:
        message["function_call"] = function
    response = {"choices": [{"message": message}]}
    if reported_usage:
        response["usage"] = {"prompt_tokens": 0, "completion_tokens": 0}
    server = http_server([Response(body=json.dumps(response).encode())])
    tool = PromptMessageTool(
        name="weather", description="Get weather", parameters={"type": "object"}
    )

    model = OAICompatLargeLanguageModel([])
    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", len)
    invocation = model.invoke(
        "model",
        {
            "mode": "chat",
            "endpoint_url": server.url,
            "function_calling_type": calling_type,
        },
        [UserPromptMessage(content="Weather?")],
        tools=[tool],
        stream=False,
    )
    if include_content and reported_usage:
        chunks = list(invocation)
        call = chunks[-1].delta.message.tool_calls[0]
        assert chunks[-1].delta.message.content is None
        assert call.function.name == "weather"
        assert json.loads(call.function.arguments) == {"city": "北京"}
        usage = chunks[-1].delta.usage
        assert usage is not None
        assert (usage.prompt_tokens, usage.completion_tokens) == (0, 0)
    else:
        with pytest.raises(InvokeError) as exc_info:
            list(invocation)
        assert isinstance(
            exc_info.value.__cause__, KeyError if not include_content else ValueError
        )
    assert model.started_at == 0
    payload = json.loads(server.requests[0].body)
    if calling_type == "tool_call":
        assert payload["tools"] == [{"type": "function", "function": tool.model_dump()}]
    else:
        assert payload["functions"] == [tool.model_dump()]


@pytest.mark.parametrize(
    ("delimiter", "configured"), [("\n\n", "\n\n"), ("\n", r"\n"), ("|", "|")]
)
@pytest.mark.parametrize(
    "content_type", ["text/event-stream", "application/octet-stream"]
)
def test_stream_decodes_fragmented_utf8_and_configured_delimiters(
    http_server: HTTPServerFactory,
    delimiter: str,
    configured: str,
    content_type: str,
) -> None:
    events = [
        ": keepalive",
        'data: {"choices":[{"delta":{"reasoning_content":"想"}}]}',
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"content":"回答😀"},"finish_reason":"stop"}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":0,"completion_tokens":2}}',
        "data: [DONE]",
        "data: invalid-after-done",
    ]
    body = (delimiter.join(events) + delimiter).encode()
    server = http_server([
        Response(
            headers={"Content-Type": content_type},
            chunks=tuple(body[index : index + 1] for index in range(len(body))),
        )
    ])
    model = OAICompatLargeLanguageModel([])

    chunks = list(
        model.invoke(
            "model",
            {
                "mode": "chat",
                "endpoint_url": server.url,
                "stream_mode_delimiter": configured,
            },
            [UserPromptMessage(content="Question")],
        )
    )

    assert (
        "".join(chunk.delta.message.content or "" for chunk in chunks)
        == "<think>\n想\n</think>回答😀"
    )
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 2
    assert model.started_at == 0


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [401, 429, 503])
def test_http_errors_reach_public_invoke_and_clear_timing(
    http_server: HTTPServerFactory, stream: bool, status: int
) -> None:
    server = http_server([Response(status=status, body=b"upstream rejected request")])
    model = OAICompatLargeLanguageModel([])

    with pytest.raises(InvokeError, match=f"{status}: upstream rejected request"):
        list(
            model.invoke(
                "model",
                {"mode": "chat", "endpoint_url": server.url},
                [UserPromptMessage(content="Question")],
                stream=stream,
            )
        )

    assert model.started_at == 0


@pytest.mark.parametrize(
    "error", [b"{broken", b'{"error":{"message":"upstream failed"}}']
)
def test_stream_errors_after_content_do_not_report_success(
    http_server: HTTPServerFactory, error: bytes
) -> None:
    server = http_server([
        Response(
            chunks=(
                b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
                b"data: " + error + b"\n\n",
            )
        )
    ])
    model = OAICompatLargeLanguageModel([])
    stream = model.invoke(
        "model",
        {"mode": "chat", "endpoint_url": server.url},
        [UserPromptMessage(content="Question")],
    )

    assert next(stream).delta.message.content == "partial"
    with pytest.raises(InvokeError):
        next(stream)
    assert model.started_at == 0


@pytest.mark.parametrize("ending", [b"", b"\n\n", b"\n\ndata:   [DONE]\n\n"])
def test_complete_http_response_keeps_eof_and_done_acceptance(
    http_server: HTTPServerFactory,
    ending: bytes,
) -> None:
    server = http_server([
        Response(
            chunks=(
                (
                    b'data: {"choices":[{"delta":{"content":"partial"},'
                    b'"finish_reason":null}]}'
                )
                + ending,
            )
        )
    ])
    model = OAICompatLargeLanguageModel([])
    stream = model.invoke(
        "model",
        {"mode": "chat", "endpoint_url": server.url},
        [UserPromptMessage(content="Question")],
    )

    assert next(stream).delta.message.content == "partial"
    terminal = next(stream)
    assert terminal.delta.message == AssistantPromptMessage(content="")
    assert terminal.delta.finish_reason is None
    assert terminal.delta.usage is not None
    assert list(stream) == []
    assert model.started_at == 0


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("calling_type", ["tool_call", "function_call", "no_call"])
def test_missing_usage_keeps_estimates_and_provider_response_overrides(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
    calling_type: str,
) -> None:
    response = (
        Response(
            chunks=(
                (
                    b'data: {"choices":[{"delta":{"content":"Answer"},'
                    b'"finish_reason":"stop"}]}\n\n'
                ),
            )
        )
        if stream
        else Response(body=b'{"choices":[{"message":{"content":"Answer"}}]}')
    )
    server = http_server([response])
    model = LegacyResponseLLM([])
    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", len)
    prompts = [UserPromptMessage(content="Question")]
    tools = [
        PromptMessageTool(
            name="search",
            description="Search documentation. " * 100,
            parameters={"type": "object"},
        )
    ]
    credentials = {
        "mode": "chat",
        "endpoint_url": server.url,
        "function_calling_type": calling_type,
        "input_price": "1",
        "unit": "0.001",
    }
    expected = 18 if stream else 285

    chunks = list(
        model.invoke("model", credentials, prompts, tools=tools, stream=stream)
    )

    usage = chunks[-1].delta.usage
    assert usage is not None
    assert usage.prompt_tokens == expected
    assert usage.prompt_price == Decimal(expected) * Decimal("0.001")
    payload = json.loads(server.requests[0].body)
    if calling_type == "tool_call":
        assert payload["tools"][0]["function"]["description"] == tools[0].description
    elif calling_type == "function_call":
        assert payload["functions"][0]["description"] == tools[0].description
    else:
        assert "tools" not in payload
        assert "functions" not in payload


@pytest.mark.parametrize(
    ("mode", "stream"), [("chat", False), ("completion", False), ("chat", True)]
)
def test_validate_credentials_uses_configured_endpoint_and_mode(
    http_server: HTTPServerFactory, mode: str, stream: bool
) -> None:
    server = http_server([Response(body=b"unused stream body" if stream else b"{}")])
    OAICompatLargeLanguageModel([]).validate_credentials(
        "model",
        {
            "mode": mode,
            "endpoint_url": f"{server.url}/v1",
            "stream_mode_auth": "use" if stream else "not_use",
            "validate_credentials_max_tokens": 7,
            "extra_headers": {"X-Dify-App-Id": "app-1"},
        },
    )

    request = server.requests[0]
    payload = json.loads(request.body)
    assert request.path == (
        "/v1/chat/completions" if mode == "chat" else "/v1/completions"
    )
    assert request.headers["X-Dify-App-Id"] == "app-1"
    assert "Authorization" not in request.headers
    assert payload["max_tokens"] == 7
    assert bool(payload.get("stream")) is stream


@pytest.mark.parametrize(
    "response",
    [
        Response(status=401, body=b"invalid credentials"),
        Response(body=b"not json"),
        Response(body=b'{"object":"embedding"}'),
        Response(body=b"[]"),
    ],
)
def test_validate_credentials_rejects_http_and_response_errors(
    http_server: HTTPServerFactory, response: Response
) -> None:
    server = http_server([response])
    with pytest.raises(CredentialsValidateFailedError):
        OAICompatLargeLanguageModel([]).validate_credentials(
            "model", {"mode": "chat", "endpoint_url": server.url}
        )


def test_stream_early_close_releases_the_http_response(
    http_server: HTTPServerFactory, http_responses: tuple[list[HTTPResponse], Event]
) -> None:
    responses, _ready = http_responses
    server = http_server([
        Response(
            chunks=(
                b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
                b"data: [DONE]\n\n",
            )
        )
    ])
    model = OAICompatLargeLanguageModel([])
    stream = model.invoke(
        "model",
        {"mode": "chat", "endpoint_url": server.url},
        [UserPromptMessage(content="Question")],
    )

    assert next(stream).delta.message.content == "partial"
    stream.close()

    assert responses[0].raw.closed
    assert model.started_at == 0


def test_stream_greenlet_cancellation_releases_the_http_response(
    http_server: HTTPServerFactory, http_responses: tuple[list[HTTPResponse], Event]
) -> None:
    responses, ready = http_responses
    server = http_server([Response(chunks=(b"data: [DONE]\n\n",), delay=10)])
    model = OAICompatLargeLanguageModel([])
    worker = gevent.spawn(
        list,
        model.invoke(
            "model",
            {"mode": "chat", "endpoint_url": server.url},
            [UserPromptMessage(content="Question")],
        ),
    )
    try:
        assert ready.wait(timeout=2), "The HTTP response was not received"
    finally:
        worker.kill(timeout=2)

    assert worker.ready()
    assert responses[0].raw.closed
    assert model.started_at == 0


def test_stream_read_timeout_closes_the_response_and_clears_timing(
    http_server: HTTPServerFactory,
    http_responses: tuple[list[HTTPResponse], Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses, _ready = http_responses
    server = http_server([Response(chunks=(b"data: [DONE]\n\n",), delay=10)])
    monkeypatch.setattr(
        llm,
        "_plugin_config",
        llm._plugin_config.model_copy(update={"MAX_REQUEST_TIMEOUT": 1}),
    )
    model = OAICompatLargeLanguageModel([])

    with pytest.raises(InvokeError, match="timed out"):
        list(
            model.invoke(
                "model",
                {"mode": "chat", "endpoint_url": server.url},
                [UserPromptMessage(content="Question")],
            )
        )

    assert responses[0].raw.closed
    assert model.started_at == 0


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        b"[]",
        b'{"choices":[]}',
        b'{"choices":[{}],"usage":{"prompt_tokens":11,"completion_tokens":0}}',
    ],
)
def test_non_stream_malformed_response_fails_without_leaking_timing(
    http_server: HTTPServerFactory, body: bytes
) -> None:
    server = http_server([Response(body=body)])
    model = OAICompatLargeLanguageModel([])
    with pytest.raises(InvokeError):
        list(
            model.invoke(
                "model",
                {"mode": "chat", "endpoint_url": server.url},
                [UserPromptMessage(content="Question")],
                stream=False,
            )
        )
    assert model.started_at == 0


def test_redirect_preserves_the_request_body(http_server: HTTPServerFactory) -> None:
    server = http_server([
        Response(status=307, headers={"Location": "/v2/chat/completions"}),
        Response(
            body=b'{"choices":[{"message":{"content":"answer"}}],"usage":{"prompt_tokens":1,"completion_tokens":1}}'
        ),
    ])

    chunks = list(
        OAICompatLargeLanguageModel([]).invoke(
            "model",
            {"mode": "chat", "endpoint_url": server.url, "api_key": "key"},
            [UserPromptMessage(content="Question")],
            stream=False,
        )
    )

    assert chunks[0].delta.message.content == "answer"
    first, redirected = server.requests
    assert redirected.path == "/v2/chat/completions"
    assert redirected.method == "POST"
    assert redirected.body == first.body
    assert redirected.headers["Authorization"] == "Bearer key"


@pytest.mark.parametrize(
    ("newline", "prefix"),
    [
        ("\n", ""),
        ("\r\n", ""),
        ("\r", ""),
        ("\n", ": keepalive\n"),
        ("\n", "event: message\n"),
        ("\n", "vendor: ignored\n"),
        ("\n", "unknown field without a colon\n"),
    ],
    ids=["lf", "crlf", "cr", "leading-comment", "event-type", "unknown", "bare-field"],
)
def test_stream_preserves_data_among_sse_comments_and_ignored_fields(
    http_server: HTTPServerFactory,
    http_responses: tuple[list[HTTPResponse], Event],
    newline: str,
    prefix: str,
) -> None:
    responses, _ready = http_responses
    events = [
        "id: 1",
        "retry: 1000",
        "vendor: ignored",
        "unknown field without a colon",
        prefix
        + 'data: {"choices":[{"delta":{"content":"Answer"},"finish_reason":"stop"}]}'
        + "\n: trailing comment\nvendor: ignored",
        (
            ': keepalive\ndata: {"choices":[],"usage":'
            '{"prompt_tokens":1,"completion_tokens":2}}'
        ),
        ": keepalive\nvendor: ignored\ndata: [DONE]",
        "data: invalid-after-done",
        "",
    ]
    body = "\n\n".join(events).replace("\n", newline).encode()
    server = http_server([
        Response(
            headers={"Content-Type": "text/event-stream"},
            chunks=tuple(
                body[offset : offset + 3] for offset in range(0, len(body), 3)
            ),
        )
    ])
    model = OAICompatLargeLanguageModel([])

    try:
        chunks = list(
            model.invoke(
                "model",
                {"mode": "chat", "endpoint_url": server.url},
                [UserPromptMessage(content="Question")],
            )
        )
    finally:
        assert responses[0].raw.closed
        assert model.started_at == 0

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == "Answer"
    )
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 3


@pytest.mark.parametrize("charset", ["utf-8", "gbk", "utf-16"])
def test_stream_preserves_explicit_response_charset(
    http_server: HTTPServerFactory, charset: str
) -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"回答"},"finish_reason":"stop"}]}'
        '\n\ndata: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":2}}'
        "\n\ndata: [DONE]\n\n"
    ).encode(charset)
    server = http_server([
        Response(
            headers={"Content-Type": f"text/event-stream; charset={charset}"},
            chunks=tuple(body[index : index + 1] for index in range(len(body))),
        )
    ])
    model = OAICompatLargeLanguageModel([])

    chunks = list(
        model.invoke(
            "model",
            {"mode": "chat", "endpoint_url": server.url},
            [UserPromptMessage(content="Question")],
        )
    )

    assert "".join(chunk.delta.message.get_text_content() for chunk in chunks) == "回答"
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 3
    assert model.started_at == 0


@pytest.mark.parametrize("delimiter", ["\n\n", "|"])
@pytest.mark.parametrize("prefix", ["", "data: "])
def test_stream_preserves_raw_and_single_prefix_multiline_json(
    http_server: HTTPServerFactory, delimiter: str, prefix: str
) -> None:
    payload = {
        "choices": [{"delta": {"content": "Answer"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    body = prefix + json.dumps(payload, indent=2) + delimiter + "[DONE]" + delimiter
    server = http_server([Response(body=body.encode())])
    model = OAICompatLargeLanguageModel([])

    chunks = list(
        model.invoke(
            "model",
            {
                "mode": "chat",
                "endpoint_url": server.url,
                "stream_mode_delimiter": delimiter,
            },
            [UserPromptMessage(content="Question")],
        )
    )

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == "Answer"
    )
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 3
    assert model.started_at == 0


@pytest.mark.parametrize("delimiter", ["\n\n", "|"])
@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "0",
        "false",
        '"text"',
        "[1]",
        '{"broken":',
        '{"choices":\n\n}',
        "[\n\n1\n\n]",
    ],
)
def test_stream_keeps_errors_for_raw_nonobject_frames(
    http_server: HTTPServerFactory,
    http_responses: tuple[list[HTTPResponse], Event],
    delimiter: str,
    raw: str,
) -> None:
    responses, _ready = http_responses
    body = (
        'data: {"choices":[{"delta":{"content":"partial"}}]}'
        + delimiter
        + raw
        + delimiter
    ).encode()
    server = http_server([Response(body=body)])
    model = OAICompatLargeLanguageModel([])
    stream = model.invoke(
        "model",
        {
            "mode": "chat",
            "endpoint_url": server.url,
            "stream_mode_delimiter": delimiter,
        },
        [UserPromptMessage(content="Question")],
    )

    assert next(stream).delta.message.content == "partial"
    with pytest.raises(InvokeError, match="Invalid JSON"):
        next(stream)
    assert responses[0].raw.closed
    assert model.started_at == 0


def test_completion_stream_handles_empty_text_and_partial_usage(
    http_server: HTTPServerFactory,
) -> None:
    frames = [
        {"choices": [{"text": ""}]},
        {"choices": [{"text": "An"}]},
        {"choices": [{"text": ""}]},
        {"choices": [{"text": "swer"}]},
        {
            "choices": [{"text": "", "finish_reason": "length"}],
            "usage": {"prompt_tokens": 0},
        },
    ]
    body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
    server = http_server([Response(body=(body + "data: [DONE]\n\n").encode())])
    model = OAICompatLargeLanguageModel([])

    chunks = list(
        model.invoke(
            "model",
            {"mode": "completion", "endpoint_url": server.url},
            [UserPromptMessage(content="Question")],
        )
    )

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == "Answer"
    )
    assert chunks[-1].delta.finish_reason == "length"
    usage = chunks[-1].delta.usage
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (
        0,
        1,
        1,
    )
    assert model.started_at == 0


@pytest.mark.parametrize("stream", [False, True])
def test_missing_usage_can_estimate_tools_with_integer_enum_parameters(
    http_server: HTTPServerFactory, stream: bool
) -> None:
    response = (
        Response(
            body=b'data: {"choices":[{"delta":{"content":"Answer"},'
            b'"finish_reason":"stop"}]}\n\n'
            b"data: [DONE]\n\n"
        )
        if stream
        else Response(body=b'{"choices":[{"message":{"content":"Answer"}}]}')
    )
    server = http_server([response])
    model = OAICompatLargeLanguageModel([])
    tool = PromptMessageTool(
        name="configure",
        description="Choose the number of attempts",
        parameters={
            "type": "object",
            "properties": {"attempts": {"type": "integer", "enum": [1, 2]}},
            "required": ["attempts"],
        },
    )

    chunks = list(
        model.invoke(
            "model",
            {
                "mode": "chat",
                "endpoint_url": server.url,
                "function_calling_type": "tool_call",
            },
            [UserPromptMessage(content="Configure two attempts")],
            tools=[tool],
            stream=stream,
        )
    )

    assert (
        "".join(chunk.delta.message.get_text_content() for chunk in chunks) == "Answer"
    )
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.prompt_tokens > 0
    payload = json.loads(server.requests[0].body)
    assert payload["tools"] == [{"type": "function", "function": tool.model_dump()}]
    assert model.started_at == 0
