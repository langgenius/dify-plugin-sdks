from decimal import Decimal

import pytest
from pydantic import ValidationError

from dify_plugin.core.entities.plugin.request import (
    ModelActions,
    ModelInvokeMultimodalEmbeddingRequest,
    ModelInvokeMultimodalRerankRequest,
    PluginInvokeType,
)
from dify_plugin.entities.model import EmbeddingInputType, ModelType
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    MultiModalContent,
    MultiModalContentType,
    MultiModalEmbeddingResult,
    TextEmbeddingResult,
)
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel


def test_multimodal_content_type_coercion():
    content = MultiModalContent(content="hello", content_type="text")

    assert content.content_type is MultiModalContentType.TEXT


def test_multimodal_content_invalid_type():
    with pytest.raises(ValidationError):
        MultiModalContent(content="invalid", content_type="audio")


def test_multimodal_embedding_request_defaults():
    request = ModelInvokeMultimodalEmbeddingRequest(
        type=PluginInvokeType.Model,
        action=ModelActions.InvokeMultimodalEmbedding,
        user_id="user",
        provider="provider",
        model_type=ModelType.TEXT_EMBEDDING,
        model="model",
        credentials={},
        tenant_id="tenant",
        documents=[{"content": "data", "content_type": "image"}],
    )

    assert request.input_type is EmbeddingInputType.DOCUMENT
    assert isinstance(request.documents[0], MultiModalContent)
    assert request.documents[0].content_type is MultiModalContentType.IMAGE


def test_multimodal_rerank_request_parsing():
    request = ModelInvokeMultimodalRerankRequest(
        type=PluginInvokeType.Model,
        action=ModelActions.InvokeMultimodalRerank,
        user_id="user",
        provider="provider",
        model_type=ModelType.RERANK,
        model="model",
        credentials={},
        query={"content": "question", "content_type": "text"},
        docs=[{"content": "document", "content_type": "text"}],
        score_threshold=0.5,
        top_n=2,
    )

    assert isinstance(request.query, MultiModalContent)
    assert request.query.content == "question"
    assert request.docs[0].content == "document"


class MockTextEmbeddingModel(TextEmbeddingModel):
    def __init__(self):
        super().__init__(model_schemas=[])
        self.multimodal_calls: list[tuple] = []

    def validate_credentials(self, model: str, credentials: dict) -> None:
        return None

    @property
    def _invoke_error_mapping(self):  # type: ignore[override]
        return {}

    def _usage(self) -> EmbeddingUsage:
        return EmbeddingUsage(
            tokens=1,
            total_tokens=1,
            unit_price=Decimal("0"),
            price_unit=Decimal("1"),
            total_price=Decimal("0"),
            currency="USD",
            latency=0.0,
        )

    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        return TextEmbeddingResult(
            model=model,
            embeddings=[[float(index) + 1.0] for index, _ in enumerate(texts)],
            usage=self._usage(),
        )

    def _invoke_multimodal(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        documents: list[MultiModalContent],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> MultiModalEmbeddingResult:
        self.multimodal_calls.append((model, tenant_id, credentials, documents, user, input_type))
        return MultiModalEmbeddingResult(model=model, embeddings=[[0.1, 0.2]], usage=self._usage())

    def get_num_tokens(self, model: str, credentials: dict, texts: list[str]) -> list[int]:
        return [len(text) for text in texts]


def test_text_embedding_model_invoke_multimodal_success():
    model = MockTextEmbeddingModel()
    documents = [MultiModalContent(content="hello", content_type=MultiModalContentType.TEXT)]

    result = model.invoke_multimodal(
        model="mock-model",
        tenant_id="tenant",
        credentials={"api_key": "test"},
        documents=documents,
        user="user",
        input_type=EmbeddingInputType.QUERY,
    )

    assert result.model == "mock-model"
    assert result.embeddings == [[0.1, 0.2]]
    assert model.multimodal_calls[0] == (
        "mock-model",
        "tenant",
        {"api_key": "test"},
        documents,
        "user",
        EmbeddingInputType.QUERY,
    )
