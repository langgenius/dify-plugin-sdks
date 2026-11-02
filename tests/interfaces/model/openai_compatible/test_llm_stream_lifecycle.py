import json
from collections.abc import Generator, Iterable, Iterator
from unittest.mock import MagicMock

import pytest
import requests
from hypothesis import given
from hypothesis import strategies as st

from dify_plugin.core.utils import http
from dify_plugin.entities.model.llm import LLMResultChunk
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


def _event(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()


def _choice(delta: dict, finish_reason: str | None = None) -> bytes:
    return _event({"choices": [{"delta": delta, "finish_reason": finish_reason}]})


ZERO_USAGE = _event({
    "choices": [],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
})


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> Generator[OAICompatLargeLanguageModel]:
    model = OAICompatLargeLanguageModel([])

    def unexpected_token_estimate(_text: str) -> int:
        pytest.fail("The stream already supplied token counts")

    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", unexpected_token_estimate)
    with model.timing_context():
        yield model


def _response(events: Iterable[bytes]) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.encoding = "utf-8"
    response.raw = MagicMock()
    response.raw.stream.return_value = iter(events)
    response.close = MagicMock(wraps=response.close)
    return response


def _stream(
    llm: OAICompatLargeLanguageModel, response: requests.Response
) -> Generator[LLMResultChunk]:
    return llm._handle_generate_stream_response(
        model="model",
        credentials={},
        response=response,
        prompt_messages=[UserPromptMessage(content="Question")],
    )


@pytest.mark.parametrize("finish_reason", ["stop", "length"])
def test_stream_preserves_finish_reason_after_heartbeats(
    llm: OAICompatLargeLanguageModel, finish_reason: str
) -> None:
    response = _response([
        _choice({"reasoning_content": "A"}),
        _choice({"content": "Answer"}, finish_reason),
        _choice({}),
        _event({"choices": [{"delta": {}}]}),
        ZERO_USAGE,
        b"data: [DONE]\n\n",
    ])

    chunks = list(_stream(llm, response))

    assert "".join(chunk.delta.message.content for chunk in chunks) == (
        "<think>\nA\n</think>Answer"
    )
    assert chunks[-1].delta.finish_reason == finish_reason
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 0
    response.close.assert_called_once()


def test_done_stops_reading_and_closes_response(
    llm: OAICompatLargeLanguageModel,
) -> None:
    def events() -> Iterator[bytes]:
        yield _choice({"reasoning_content": "A"}, "stop")
        yield ZERO_USAGE
        yield b": heartbeat\nvendor: ignored\ndata: [DONE]\n\n"
        pytest.fail("The response must not be read after [DONE]")

    response = _response(events())

    chunks = list(_stream(llm, response))

    assert "".join(chunk.delta.message.content for chunk in chunks) == (
        "<think>\nA\n</think>"
    )
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage is not None
    assert chunks[-1].delta.usage.total_tokens == 0
    response.close.assert_called_once()


def test_stream_closes_response_at_eof(llm: OAICompatLargeLanguageModel) -> None:
    response = _response([
        _choice({"reasoning_content": "A"}, "length"),
        ZERO_USAGE,
    ])

    chunks = list(_stream(llm, response))

    assert "".join(chunk.delta.message.content for chunk in chunks) == (
        "<think>\nA\n</think>"
    )
    assert chunks[-1].delta.finish_reason == "length"
    assert chunks[-1].delta.usage is not None
    response.close.assert_called_once()


def test_stream_closes_response_when_cancelled(
    llm: OAICompatLargeLanguageModel,
) -> None:
    response = _response([_choice({"reasoning_content": "A"}), ZERO_USAGE])
    stream = _stream(llm, response)

    assert next(stream).delta.message.content == "<think>\nA"
    stream.close()

    response.close.assert_called_once()


def test_stream_closes_response_when_delimiter_is_invalid(
    llm: OAICompatLargeLanguageModel,
) -> None:
    response = _response([])

    with pytest.raises(UnicodeDecodeError):
        list(
            llm._handle_generate_stream_response(
                model="model",
                credentials={"stream_mode_delimiter": "\\"},
                response=response,
                prompt_messages=[],
            )
        )

    response.close.assert_called_once()


@pytest.mark.parametrize("stream", [False, True])
def test_generate_closes_http_error_response(
    llm: OAICompatLargeLanguageModel,
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
) -> None:
    response = _response([b"upstream unavailable"])
    response.status_code = 503
    monkeypatch.setattr(http, "post", lambda *_args, **_kwargs: response)

    with pytest.raises(InvokeError, match="503: upstream unavailable"):
        llm._generate(
            "model",
            {"mode": "chat", "endpoint_url": "https://example.com/v1"},
            [UserPromptMessage(content="Question")],
            {},
            stream=stream,
        )

    response.close.assert_called_once()


def test_generate_closes_non_stream_response(
    llm: OAICompatLargeLanguageModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = _response([
        json.dumps({
            "choices": [{"message": {"content": "Answer"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }).encode()
    ])
    monkeypatch.setattr(http, "post", lambda *_args, **_kwargs: response)

    result = llm._generate(
        "model",
        {"mode": "chat", "endpoint_url": "https://example.com/v1"},
        [UserPromptMessage(content="Question")],
        {},
        stream=False,
    )

    assert result.message.content == "Answer"
    assert result.usage.total_tokens == 0
    response.close.assert_called_once()


@pytest.mark.parametrize(
    "error_event",
    [
        b"data: {broken\n\n",
        _event({"error": {"message": "upstream failed"}}),
        _event({"choices": [], "error": {"message": "upstream failed"}}),
        _event({"choices": None, "error": {"message": "upstream failed"}}),
    ],
    ids=["invalid-json", "error", "error-empty-choices", "error-null-choices"],
)
def test_stream_error_does_not_yield_success(
    llm: OAICompatLargeLanguageModel, error_event: bytes
) -> None:
    response = _response([
        ZERO_USAGE,
        _choice({"reasoning_content": "A"}),
        error_event,
    ])
    chunks: list[LLMResultChunk] = []

    with pytest.raises(InvokeError):
        chunks.extend(_stream(llm, response))

    assert len(chunks) == 1
    assert chunks[0].delta.message.content == "<think>\nA"
    assert all(chunk.delta.usage is None for chunk in chunks)
    response.close.assert_called_once()


def test_stream_closes_response_on_read_error(
    llm: OAICompatLargeLanguageModel,
) -> None:
    def events() -> Iterator[bytes]:
        yield _choice({"reasoning_content": "A"})
        message = "stream disconnected"
        raise requests.ConnectionError(message)

    response = _response(events())
    chunks: list[LLMResultChunk] = []

    with pytest.raises(requests.ConnectionError, match="stream disconnected"):
        chunks.extend(_stream(llm, response))

    assert len(chunks) == 1
    assert chunks[0].delta.usage is None
    response.close.assert_called_once()


@pytest.mark.parametrize("prompt_tokens", [0, 3])
def test_stream_merges_partial_usage_without_losing_counts(
    llm: OAICompatLargeLanguageModel, prompt_tokens: int
) -> None:
    response = _response([
        _choice({"reasoning_content": "A"}),
        _choice({"content": "Answer"}, "stop"),
        _event({
            "choices": [],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 7},
        }),
        _event({
            "choices": [],
            "usage": {"prompt_tokens": None, "completion_tokens": 0},
        }),
        _event({"choices": [], "usage": {"completion_tokens": None}}),
        _event({"choices": [], "usage": None}),
        _event({"choices": [], "usage": {}}),
        b"data: [DONE]\n\n",
    ])

    chunks = list(_stream(llm, response))

    usage = chunks[-1].delta.usage
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens) == (prompt_tokens, 0)
    assert usage.total_tokens == prompt_tokens
    assert chunks[-1].delta.finish_reason == "stop"
    response.close.assert_called_once()


@given(
    content=st.text(alphabet=st.characters(exclude_categories=("Cs",)), max_size=100),
    sizes=st.lists(st.integers(min_value=1, max_value=32), min_size=1, max_size=20),
    newline=st.sampled_from(["\n", "\r\n", "\r"]),
)
def test_stream_decoding_is_independent_of_byte_boundaries(
    content: str,
    sizes: list[int],
    newline: str,
) -> None:
    payload = {"choices": [{"delta": {"content": content}, "finish_reason": "stop"}]}
    data_lines = "\n: heartbeat\nvendor: ignored\n".join(
        f"data: {line}"
        for line in json.dumps(payload, ensure_ascii=False, indent=2).split("\n")
    )
    body = (
        (
            f"\ufeff: heartbeat\nevent: message\nid: 1\n{data_lines}\n\n"
            "id: 2\n\n" + ZERO_USAGE.decode() + "data: [DONE]\n\n"
        )
        .replace("\n", newline)
        .encode()
    )
    fragments = []
    offset = 0
    for size in sizes:
        fragments.append(body[offset : offset + size])
        offset += size
    fragments.append(body[offset:])
    response = _response(fragments)
    model = OAICompatLargeLanguageModel([])

    with model.timing_context():
        chunks = list(_stream(model, response))

    assert "".join(chunk.delta.message.content for chunk in chunks) == content
    assert chunks[-1].delta.finish_reason == "stop"
    assert chunks[-1].delta.usage.total_tokens == 0
    response.close.assert_called_once()
