from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import gevent
import pytest
from gevent.event import Event

import dify_plugin
from dify_plugin.core.entities.plugin.request import (
    ModelInvokeLLMRequest,
    ModelInvokeTextEmbeddingRequest,
)
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.core.session_context import get_current_session, use_current_session
from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from tests.servers.helpers import MemoryRequestReader, RecordingResponseWriter


def _session(app_id: str = "app-1") -> Session:
    return Session(
        session_id=f"session-{app_id}",
        executor=MagicMock(spec=ThreadPoolExecutor),
        reader=MemoryRequestReader(),
        writer=RecordingResponseWriter(),
        app_id=app_id,
    )


def _executor(model: object) -> PluginExecutor:
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    return PluginExecutor(config=MagicMock(), registration=registration)


def _llm_data() -> ModelInvokeLLMRequest:
    return ModelInvokeLLMRequest.model_validate({
        "provider": "provider",
        "model_type": "llm",
        "model": "model",
        "credentials": {},
        "prompt_messages": [{"role": "user", "content": "hello"}],
        "model_parameters": {},
        "tools": None,
        "stop": None,
        "stream": True,
        "user_id": "user",
    })


def _text_embedding_data() -> ModelInvokeTextEmbeddingRequest:
    return ModelInvokeTextEmbeddingRequest.model_validate({
        "type": "model",
        "action": "invoke_text_embedding",
        "user_id": "user",
        "provider": "provider",
        "model_type": "text-embedding",
        "model": "model",
        "credentials": {},
        "texts": ["hello"],
        "input_type": "query",
    })


def test_get_current_session_is_public() -> None:
    assert dify_plugin.get_current_session is get_current_session
    assert "get_current_session" in dify_plugin.__all__


def test_llm_stream_keeps_session_until_consumed() -> None:
    seen: list[Session | None] = []

    def stream() -> Generator[str, None, None]:
        seen.append(get_current_session())
        yield "chunk"

    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.return_value = stream()

    result = _executor(model).invoke_llm(_session(), _llm_data())

    assert get_current_session() is None
    assert list(result) == ["chunk"]
    assert seen[0] is not None
    assert seen[0].app_id == "app-1"
    assert get_current_session() is None


def test_text_embedding_forwards_input_type_and_exposes_session() -> None:
    seen: list[Session | None] = []

    def invoke(*_args: object, **_kwargs: object) -> list[str]:
        seen.append(get_current_session())
        return ["embedding"]

    model = MagicMock(spec=TextEmbeddingModel)
    model.invoke.side_effect = invoke

    assert _executor(model).invoke_text_embedding(
        _session(), _text_embedding_data()
    ) == ["embedding"]
    assert seen[0] is not None
    assert seen[0].app_id == "app-1"
    assert get_current_session() is None
    model.invoke.assert_called_once_with(
        "model",
        {},
        ["hello"],
        user="user",
        input_type=EmbeddingInputType.QUERY,
    )


@pytest.mark.parametrize("finish", ["complete", "error", "close"])
def test_llm_restores_outer_session_when_stream_finishes(finish: str) -> None:
    outer, inner = _session("outer"), _session("inner")
    seen: list[Session | None] = []

    def stream() -> Generator[str]:
        try:
            seen.append(get_current_session())
            yield "first"
            if finish == "error":
                msg = "provider disconnected"
                raise RuntimeError(msg)
            seen.append(get_current_session())
            yield "second"
        finally:
            seen.append(get_current_session())

    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.return_value = stream()
    with use_current_session(outer):
        result = _executor(model).invoke_llm(inner, _llm_data())
        assert isinstance(result, Generator)
        assert get_current_session() is outer
        try:
            assert next(result) == "first"
            if finish == "close":
                result.close()
            elif finish == "error":
                with pytest.raises(RuntimeError, match="provider disconnected"):
                    next(result)
            else:
                assert list(result) == ["second"]
            assert get_current_session() is outer
        finally:
            result.close()

    assert seen == [inner] * (3 if finish == "complete" else 2)
    assert get_current_session() is None


def test_model_creation_error_restores_outer_session() -> None:
    outer, inner = _session("outer"), _session("inner")

    def invoke(*_args: object, **_kwargs: object) -> None:
        assert get_current_session() is inner
        msg = "model rejected credentials"
        raise ValueError(msg)

    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.side_effect = invoke
    with use_current_session(outer):
        with pytest.raises(ValueError, match="model rejected credentials"):
            _executor(model).invoke_llm(inner, _llm_data())
        assert get_current_session() is outer
    assert get_current_session() is None


def test_nested_model_invocation_restores_callers_session() -> None:
    outer, inner = _session("outer"), _session("inner")

    def embed(*_args: object, **_kwargs: object) -> list[str]:
        assert get_current_session() is inner
        return ["embedding"]

    embedding = MagicMock(spec=TextEmbeddingModel)
    embedding.invoke.side_effect = embed

    def invoke(*_args: object, **_kwargs: object) -> dict[str, str]:
        assert get_current_session() is outer
        result = _executor(embedding).invoke_text_embedding(
            inner, _text_embedding_data()
        )
        assert result == ["embedding"]
        assert get_current_session() is outer
        return {"answer": "done"}

    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.side_effect = invoke
    assert _executor(model).invoke_llm(outer, _llm_data()) == {"answer": "done"}
    assert get_current_session() is None


@pytest.mark.parametrize("cancel_first", [False, True])
def test_concurrent_model_streams_isolate_sessions(cancel_first: bool) -> None:
    sessions = [_session("app-a"), _session("app-b")]
    entered = [Event(), Event()]
    resume = [Event(), Event()]
    cleaned: list[Session | None] = []

    def consume(index: int) -> list[str]:
        session = sessions[index]

        def stream() -> Generator[str]:
            try:
                assert get_current_session() is session
                yield f"{session.app_id}-first"
                entered[index].set()
                assert resume[index].wait(timeout=2), "consumer was not resumed"
                assert get_current_session() is session
                yield f"{session.app_id}-last"
            finally:
                cleaned.append(get_current_session())

        model = MagicMock(spec=LargeLanguageModel)
        model.invoke.return_value = stream()
        result = _executor(model).invoke_llm(session, _llm_data())
        assert isinstance(result, Generator)
        try:
            values = list(result)
            assert get_current_session() is None
            return values
        finally:
            result.close()

    workers = [gevent.spawn(consume, index) for index in range(2)]
    try:
        assert all(event.wait(timeout=2) for event in entered)
        assert get_current_session() is None
        if cancel_first:
            workers[0].kill(block=True, timeout=2)
            assert workers[0].dead
        else:
            resume[0].set()
            assert workers[0].get(timeout=2) == ["app-a-first", "app-a-last"]
        resume[1].set()
        assert workers[1].get(timeout=2) == ["app-b-first", "app-b-last"]
        assert cleaned == sessions
        assert get_current_session() is None
    finally:
        for event in resume:
            event.set()
        gevent.killall(workers, block=True, timeout=2)
