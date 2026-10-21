from collections.abc import Generator
from unittest.mock import patch

import pytest

from dify_plugin.entities.model.llm import LLMResultChunk, LLMResultChunkDelta
from dify_plugin.entities.model.message import AssistantPromptMessage
from dify_plugin.errors.model import (
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
)
from tests.interfaces.model.utils import StubLLM


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (TimeoutError("stream timed out"), InvokeConnectionError),
        (RuntimeError("provider stream failed"), InvokeError),
        (InvokeRateLimitError(description="rate limited"), InvokeRateLimitError),
    ],
)
def test_invoke_maps_errors_after_stream_starts(
    error: Exception,
    expected_type: type[InvokeError],
) -> None:
    llm = StubLLM([])
    first_chunk = LLMResultChunk(
        model="model",
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(content="<think>\nA"),
        ),
    )
    expected_chunk = first_chunk.model_copy(deep=True)

    def response() -> Generator[LLMResultChunk, None, None]:
        yield first_chunk
        raise error

    with patch.object(llm, "_invoke", return_value=response()):
        stream = llm.invoke(model="model", credentials={}, prompt_messages=[])
        assert next(stream) == expected_chunk
        assert llm.started_at > 0

        with pytest.raises(expected_type) as exc_info:
            next(stream)

    if isinstance(error, InvokeError):
        assert exc_info.value is error
    else:
        assert exc_info.value.__cause__ is error
    assert llm.started_at == 0


def test_invoke_closes_provider_stream() -> None:
    llm = StubLLM([])
    closed = False

    def response() -> Generator[LLMResultChunk, None, None]:
        nonlocal closed
        try:
            yield LLMResultChunk(
                model="model",
                delta=LLMResultChunkDelta(
                    index=0,
                    message=AssistantPromptMessage(content="<think>\nA"),
                ),
            )
        finally:
            closed = True

    with patch.object(llm, "_invoke", return_value=response()):
        stream = llm.invoke(model="model", credentials={}, prompt_messages=[])
        next(stream)
        stream.close()

    assert closed
    assert llm.started_at == 0


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (TimeoutError("request timed out"), InvokeConnectionError),
        (RuntimeError("provider failed"), InvokeError),
        (InvokeRateLimitError(description="rate limited"), InvokeRateLimitError),
    ],
)
def test_invoke_maps_errors_before_first_chunk(
    error: Exception,
    expected_type: type[InvokeError],
) -> None:
    llm = StubLLM([])

    with (
        patch.object(llm, "_invoke", side_effect=error),
        pytest.raises(expected_type) as exc_info,
    ):
        list(llm.invoke(model="model", credentials={}, prompt_messages=[]))

    if isinstance(error, InvokeError):
        assert exc_info.value is error
    else:
        assert exc_info.value.__cause__ is error
    assert llm.started_at == 0


def test_empty_llm_stream_finishes_and_resets_timing() -> None:
    llm = StubLLM([])

    def response() -> Generator[LLMResultChunk]:
        yield from ()

    with patch.object(llm, "_invoke", return_value=response()):
        assert list(llm.invoke(model="model", credentials={}, prompt_messages=[])) == []

    assert llm.started_at == 0


def test_closing_unstarted_llm_stream_does_not_invoke_provider() -> None:
    llm = StubLLM([])

    with patch.object(llm, "_invoke") as provider:
        stream = llm.invoke(model="model", credentials={}, prompt_messages=[])
        stream.close()

    provider.assert_not_called()
    assert llm.started_at == 0
