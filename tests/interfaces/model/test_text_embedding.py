from collections.abc import Mapping
from decimal import Decimal
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import EmbeddingInputType, ModelType
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    MultiModalContent,
    MultiModalContentType,
    MultiModalEmbeddingResult,
    TextEmbeddingResult,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel

from .utils import prepare_model_factory


class MockTextEmbeddingModel(TextEmbeddingModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        del credentials
        del user
        del input_type
        return TextEmbeddingResult(
            model=model,
            usage=EmbeddingUsage(
                tokens=0,
                total_tokens=0,
                unit_price=Decimal(0),
                price_unit=Decimal(0),
                total_price=Decimal(0),
                currency="USD",
                latency=0,
            ),
            embeddings=[[0.0] * 1536 for _ in texts],
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass

    def get_num_tokens(
        self, model: str, credentials: dict, texts: list[str]
    ) -> list[int]:
        del model
        del credentials
        return [0] * len(texts)


# test both constructor and invoke
def test_text_embedding() -> None:
    model_factory = prepare_model_factory({
        ModelType.TEXT_EMBEDDING: MockTextEmbeddingModel
    })
    instance = model_factory.get_instance(ModelType.TEXT_EMBEDDING)
    assert isinstance(instance, MockTextEmbeddingModel)
    result = instance.invoke(model="test", credentials={}, texts=["first", "second"])
    assert result.model == "test"
    assert len(result.embeddings) == 2
    assert all(len(embedding) == 1536 for embedding in result.embeddings)
    assert instance.started_at == 0


class MockMultiModalTextEmbeddingModel(TextEmbeddingModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        documents = [
            MultiModalContent(content=text, content_type=MultiModalContentType.TEXT)
            for text in texts
        ]
        result = self._invoke_multimodal(
            model, credentials, documents, user, input_type
        )

        return TextEmbeddingResult(
            model=model,
            usage=result.usage,
            embeddings=result.embeddings,
        )

    def _invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        documents: list[MultiModalContent],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> MultiModalEmbeddingResult:
        del credentials
        del user
        del input_type
        return MultiModalEmbeddingResult(
            model=model,
            usage=EmbeddingUsage(
                tokens=0,
                total_tokens=0,
                unit_price=Decimal(0),
                price_unit=Decimal(0),
                total_price=Decimal(0),
                currency="USD",
                latency=0,
            ),
            embeddings=[[0.0] * 1536 for _ in documents],
        )

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass

    def get_num_tokens(
        self, model: str, credentials: dict, texts: list[str]
    ) -> list[int]:
        del model
        del credentials
        return [0] * len(texts)

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}


def test_text_embedding_multimodal(monkeypatch: pytest.MonkeyPatch) -> None:
    model_factory = prepare_model_factory({
        ModelType.TEXT_EMBEDDING: MockMultiModalTextEmbeddingModel
    })
    instance = model_factory.get_instance(ModelType.TEXT_EMBEDDING)
    assert isinstance(instance, MockMultiModalTextEmbeddingModel)
    documents = [
        MultiModalContent(content="test", content_type=MultiModalContentType.TEXT),
        MultiModalContent(
            content="https://example.com/image.png",
            content_type=MultiModalContentType.IMAGE,
        ),
    ]
    provider = Mock(wraps=instance._invoke_multimodal)
    monkeypatch.setattr(instance, "_invoke_multimodal", provider)

    result = instance.invoke_multimodal(
        model="test",
        credentials={},
        documents=documents,
        input_type=EmbeddingInputType.QUERY,
        user="user-1",
    )

    assert result.model == "test"
    assert len(result.embeddings) == 2
    assert all(len(embedding) == 1536 for embedding in result.embeddings)
    provider.assert_called_once_with(
        "test", {}, documents, "user-1", EmbeddingInputType.QUERY
    )
    assert instance.started_at == 0


def test_embedding_without_multimodal_support_raises_not_implemented() -> None:
    instance = MockTextEmbeddingModel([])

    with pytest.raises(NotImplementedError, match="_invoke_multimodal"):
        instance.invoke_multimodal("test", {}, [])

    assert instance.started_at == 0
