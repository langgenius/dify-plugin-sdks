from collections.abc import Callable, Mapping
from io import BytesIO
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.entities.model.text_embedding import (
    MultiModalContent,
    MultiModalContentType,
)
from dify_plugin.errors.model import (
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
)
from dify_plugin.interfaces.model.ai_model import AIModel
from dify_plugin.interfaces.model.moderation_model import ModerationModel
from dify_plugin.interfaces.model.rerank_model import RerankModel
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from dify_plugin.interfaces.model.tts_model import TTSModel


class ProviderMethods:
    def _invoke(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise NotImplementedError

    _invoke_multimodal = _invoke

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    def get_num_tokens(self, *args: object) -> list[int]:
        del args
        return []

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeConnectionError: [TimeoutError],
            InvokeAuthorizationError: [PermissionError],
        }


class EmbeddingProvider(ProviderMethods, TextEmbeddingModel):
    pass


class RerankProvider(ProviderMethods, RerankModel):
    pass


class ModerationProvider(ProviderMethods, ModerationModel):
    pass


class SpeechProvider(ProviderMethods, Speech2TextModel):
    pass


class TTSProvider(ProviderMethods, TTSModel):
    pass


def test_error_mapper_keeps_sdk_errors_in_the_existing_mapping() -> None:
    model = EmbeddingProvider([])
    error = InvokeBadRequestError("invalid input")

    mapped = model._transform_invoke_error(error)
    assert type(mapped) is InvokeError
    assert str(mapped) == "[interfaces] Error: invalid input"


@pytest.fixture(
    params=[
        pytest.param((EmbeddingProvider, "invoke"), id="embedding"),
        pytest.param(
            (EmbeddingProvider, "invoke_multimodal"), id="multimodal-embedding"
        ),
        pytest.param((RerankProvider, "invoke"), id="rerank"),
        pytest.param((RerankProvider, "invoke_multimodal"), id="multimodal-rerank"),
        pytest.param((ModerationProvider, "invoke"), id="moderation"),
        pytest.param((SpeechProvider, "invoke"), id="speech-to-text"),
        pytest.param((TTSProvider, "invoke"), id="text-to-speech"),
    ],
)
def invocation(
    request: pytest.FixtureRequest,
) -> tuple[AIModel, Callable[[], object], str]:
    model_class, method_name = request.param
    model = model_class([])
    document = MultiModalContent(
        content="document", content_type=MultiModalContentType.TEXT
    )
    arguments = {
        EmbeddingProvider: {
            "texts": ["document"],
            "input_type": EmbeddingInputType.QUERY,
        },
        RerankProvider: {
            "query": "query",
            "docs": ["document"],
            "top_n": 1,
            "score_threshold": 0.5,
        },
        ModerationProvider: {"text": "hello"},
        SpeechProvider: {"file": BytesIO(b"audio")},
        TTSProvider: {"tenant_id": "tenant", "content_text": "hello", "voice": "voice"},
    }[model_class]
    if method_name == "invoke_multimodal":
        arguments = (
            {"documents": [document], "input_type": EmbeddingInputType.QUERY}
            if model_class is EmbeddingProvider
            else {
                "query": document,
                "docs": [document],
                "top_n": 1,
                "score_threshold": 0.5,
            }
        )
    method = getattr(model, method_name)

    def invoke() -> object:
        return method(model="model", credentials={}, user="user-1", **arguments)

    return (
        model,
        invoke,
        "_invoke_multimodal" if method_name == "invoke_multimodal" else "_invoke",
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("provider timeout"), InvokeConnectionError),
        (PermissionError("secret-api-key"), InvokeAuthorizationError),
        (RuntimeError("provider failed"), InvokeError),
    ],
)
def test_provider_errors_are_mapped_and_timing_is_reset(
    invocation: tuple[AIModel, Callable[[], object], str],
    error: Exception,
    expected: type[InvokeError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, invoke, provider_method = invocation
    monkeypatch.setattr(model, provider_method, Mock(side_effect=error))

    with pytest.raises(expected) as exc_info:
        invoke()

    assert type(exc_info.value) is expected
    assert exc_info.value.__cause__ is error
    assert model.started_at == 0
    if expected is InvokeAuthorizationError:
        assert "secret-api-key" not in str(exc_info.value)
    else:
        assert str(error) in str(exc_info.value)


def test_sdk_errors_reach_provider_error_overrides(
    invocation: tuple[AIModel, Callable[[], object], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, invoke, provider_method = invocation
    cause = ValueError("invalid provider input")
    error = InvokeBadRequestError("Text-to-speech input must not be empty")
    error.__cause__ = cause
    monkeypatch.setattr(model, provider_method, Mock(side_effect=error))
    mapped = InvokeConnectionError("provider-specific mapping")
    transform = Mock(return_value=mapped)
    monkeypatch.setattr(model, "_transform_invoke_error", transform)

    with pytest.raises(InvokeConnectionError) as exc_info:
        invoke()

    transform.assert_called_once_with(error)
    assert exc_info.value is mapped
    assert exc_info.value.__cause__ is error
    assert error.__cause__ is cause
    assert model.started_at == 0


def test_provider_control_flow_exceptions_are_not_model_errors(
    invocation: tuple[AIModel, Callable[[], object], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, invoke, provider_method = invocation
    error = GeneratorExit()
    monkeypatch.setattr(model, provider_method, Mock(side_effect=error))

    with pytest.raises(GeneratorExit) as exc_info:
        invoke()

    assert exc_info.value is error
    assert model.started_at == 0
