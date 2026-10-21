from collections.abc import Mapping
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.rerank import (
    MultiModalRerankResult,
    RerankDocument,
    RerankResult,
)
from dify_plugin.entities.model.text_embedding import (
    MultiModalContent,
    MultiModalContentType,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.rerank_model import RerankModel

from .utils import prepare_model_factory


class MockRerankModel(RerankModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        query: str,
        docs: list[str],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> RerankResult:
        del credentials
        del query
        del score_threshold
        del top_n
        del user
        return RerankResult(
            model=model,
            docs=[RerankDocument(index=0, text=doc, score=0) for doc in docs],
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_rerank() -> None:
    model_factory = prepare_model_factory({ModelType.RERANK: MockRerankModel})
    instance = model_factory.get_instance(ModelType.RERANK)
    assert isinstance(instance, MockRerankModel)
    result = instance.invoke(model="test", credentials={}, query="test", docs=["test"])
    assert result.model == "test"
    assert len(result.docs) == 1
    assert result.docs[0].index == 0
    assert result.docs[0].text == "test"
    assert result.docs[0].score == 0


class MockMultiModalRerankModel(RerankModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        query: str,
        docs: list[str],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> RerankResult:
        result = self._invoke_multimodal(
            model,
            credentials,
            MultiModalContent(content=query, content_type=MultiModalContentType.TEXT),
            [
                MultiModalContent(content=doc, content_type=MultiModalContentType.TEXT)
                for doc in docs
            ],
            score_threshold,
            top_n,
            user,
        )
        return RerankResult(
            model=model,
            docs=[
                RerankDocument(index=0, text=doc.text, score=0) for doc in result.docs
            ],
        )

    def _invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        query: MultiModalContent,
        docs: list[MultiModalContent],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> MultiModalRerankResult:
        del credentials
        del query
        del score_threshold
        del top_n
        del user
        return MultiModalRerankResult(
            model=model,
            docs=[RerankDocument(index=0, text=doc.content, score=0) for doc in docs],
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_rerank_multimodal(monkeypatch: pytest.MonkeyPatch) -> None:
    model_factory = prepare_model_factory({ModelType.RERANK: MockMultiModalRerankModel})
    instance = model_factory.get_instance(ModelType.RERANK)
    assert isinstance(instance, MockMultiModalRerankModel)
    query = MultiModalContent(content="query", content_type=MultiModalContentType.TEXT)
    docs = [MultiModalContent(content="test", content_type=MultiModalContentType.TEXT)]
    provider = Mock(wraps=instance._invoke_multimodal)
    monkeypatch.setattr(instance, "_invoke_multimodal", provider)

    result = instance.invoke_multimodal(
        model="test",
        credentials={},
        query=query,
        docs=docs,
        score_threshold=0.5,
        top_n=1,
        user="user-1",
    )

    assert result.model == "test"
    assert len(result.docs) == 1
    assert result.docs[0].index == 0
    assert result.docs[0].text == "test"
    assert result.docs[0].score == 0
    provider.assert_called_once_with("test", {}, query, docs, 0.5, 1, "user-1")
    assert instance.started_at == 0


def test_rerank_without_multimodal_support_raises_not_implemented() -> None:
    instance = MockRerankModel([])
    query = MultiModalContent(content="query", content_type=MultiModalContentType.TEXT)

    with pytest.raises(NotImplementedError, match="_invoke_multimodal"):
        instance.invoke_multimodal("test", {}, query, [])

    assert instance.started_at == 0
