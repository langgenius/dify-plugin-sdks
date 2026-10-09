from collections.abc import Generator
from unittest.mock import patch

import pytest
from requests.exceptions import ReadTimeout

from dify_plugin.entities.model.llm import LLMResultChunk, LLMResultChunkDelta
from dify_plugin.entities.model.message import AssistantPromptMessage
from dify_plugin.errors.model import (
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
)
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (ReadTimeout("stream timed out"), InvokeConnectionError),
        (ValueError("provider stream failed"), InvokeError),
        (InvokeRateLimitError(description="rate limited"), InvokeRateLimitError),
    ],
)
def test_invoke_maps_errors_after_stream_starts(
    error: Exception,
    expected_type: type[InvokeError],
) -> None:
    llm = OAICompatLargeLanguageModel([])
    first_chunk = LLMResultChunk(
        model="model",
        delta=LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(content="<think>\nA"),
        ),
    )

    def response() -> Generator[LLMResultChunk, None, None]:
        yield first_chunk
        raise error

    with patch.object(llm, "_invoke", return_value=response()):
        stream = llm.invoke(model="model", credentials={}, prompt_messages=[])
        assert next(stream) is first_chunk
        assert llm.started_at > 0

        with pytest.raises(expected_type) as exc_info:
            next(stream)

    if isinstance(error, InvokeError):
        assert exc_info.value is error
    else:
        assert exc_info.value.__cause__ is error
    assert llm.started_at == 0


def test_invoke_closes_provider_stream() -> None:
    llm = OAICompatLargeLanguageModel([])
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
