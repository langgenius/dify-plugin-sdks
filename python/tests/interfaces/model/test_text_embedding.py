from collections.abc import Mapping
from decimal import Decimal

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
from tests.interfaces.model.utils import prepare_model_factory


class MockTextEmbeddingModel(TextEmbeddingModel):
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

    def get_num_tokens(self, model: str, credentials: dict, texts: list[str]) -> list[int]:
        return [0] * len(texts)


# test both constructor and invoke
def test_text_embedding():
    model_factory = prepare_model_factory({ModelType.TEXT_EMBEDDING: MockTextEmbeddingModel})
    instance = model_factory.get_instance(ModelType.TEXT_EMBEDDING)
    assert isinstance(instance, MockTextEmbeddingModel)
    instance.invoke(model="test", credentials={}, texts=["test"])


class MockMultiModalTextEmbeddingModel(TextEmbeddingModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        documents = [MultiModalContent(content=text, content_type=MultiModalContentType.TEXT) for text in texts]
        result = self._invoke_multimodal(model, credentials, documents, user, input_type)

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

    def get_num_tokens(self, model: str, credentials: dict, texts: list[str]) -> list[int]:
        return [0] * len(texts)

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}


def test_text_embedding_multimodal():
    model_factory = prepare_model_factory({ModelType.TEXT_EMBEDDING: MockMultiModalTextEmbeddingModel})
    instance = model_factory.get_instance(ModelType.TEXT_EMBEDDING)
    assert isinstance(instance, MockMultiModalTextEmbeddingModel)
    result = instance.invoke(model="test", credentials={}, texts=["test"])
    assert result.model == "test"
    assert len(result.embeddings) == 1
    assert len(result.embeddings[0]) == 1536
