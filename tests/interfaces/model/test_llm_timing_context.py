from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResultChunk, LLMResultChunkDelta
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel


class MockLLM(LargeLanguageModel):
    model_type = ModelType.LLM
    rendezvous: Barrier | None = None

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> Generator[LLMResultChunk, None, None]:
        del prompt_messages, model_parameters, tools, stop, stream, user
        assert self.started_at > 0
        if self.rendezvous:
            self.rendezvous.wait(timeout=5)
        yield LLMResultChunk(
            model=model,
            delta=LLMResultChunkDelta(
                index=0,
                message=AssistantPromptMessage(content="test"),
                usage=self._calc_response_usage(model, credentials, 2, 3),
            ),
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        del model, credentials, prompt_messages, tools
        return 0


def test_llm_timing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter([10.0, 12.5])
    monkeypatch.setattr(
        "dify_plugin.interfaces.model.ai_model.time.perf_counter",
        lambda: next(timestamps),
    )
    model = MockLLM([])
    chunks = list(model.invoke(model="test", credentials={}, prompt_messages=[]))

    assert len(chunks) == 1
    assert chunks[0].delta.message.content == "test"
    assert chunks[0].delta.usage is not None
    assert chunks[0].delta.usage.latency == pytest.approx(2.5)
    assert model.started_at == 0


def test_llm_timing_context_resets_when_stream_closes() -> None:
    model = MockLLM([])
    stream = model.invoke(model="test", credentials={}, prompt_messages=[])

    assert next(stream).delta.message.content == "test"
    assert model.started_at > 0
    stream.close()

    assert model.started_at == 0


def test_llm_timing_context_is_independent_during_concurrent_streams() -> None:
    models = [MockLLM([]) for _ in range(4)]
    rendezvous = Barrier(len(models))
    for model in models:
        model.rendezvous = rendezvous

    def invoke(model: MockLLM) -> list[LLMResultChunk]:
        return list(model.invoke(model="test", credentials={}, prompt_messages=[]))

    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        results = list(executor.map(invoke, models))

    assert len(results) == len(models)
    for chunks in results:
        assert len(chunks) == 1
        assert chunks[0].delta.message.content == "test"
        assert chunks[0].delta.usage is not None
        assert chunks[0].delta.usage.latency >= 0
    assert all(model.started_at == 0 for model in models)
