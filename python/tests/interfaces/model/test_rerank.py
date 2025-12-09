from collections.abc import Mapping

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.rerank import MultiModalRerankResult, RerankDocument, RerankResult
from dify_plugin.entities.model.text_embedding import MultiModalContent, MultiModalContentType
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.rerank_model import RerankModel
from tests.interfaces.model.utils import prepare_model_factory


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
        return RerankResult(
            model=model,
            docs=[RerankDocument(index=0, text=doc, score=0) for doc in docs],
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_rerank():
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
            [MultiModalContent(content=doc, content_type=MultiModalContentType.TEXT) for doc in docs],
            score_threshold,
            top_n,
            user,
        )
        return RerankResult(
            model=model,
            docs=[RerankDocument(index=0, text=doc.text, score=0) for doc in result.docs],
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
        return MultiModalRerankResult(
            model=model,
            docs=[RerankDocument(index=0, text=doc.content, score=0) for doc in docs],
        )

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_rerank_multimodal():
    model_factory = prepare_model_factory({ModelType.RERANK: MockMultiModalRerankModel})
    instance = model_factory.get_instance(ModelType.RERANK)
    assert isinstance(instance, MockMultiModalRerankModel)
    result = instance.invoke(model="test", credentials={}, query="test", docs=["test"])
    assert result.model == "test"
    assert len(result.docs) == 1
    assert result.docs[0].index == 0
    assert result.docs[0].text == "test"
    assert result.docs[0].score == 0
