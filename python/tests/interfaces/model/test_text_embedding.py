from decimal import Decimal

from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.entities.model.text_embedding import EmbeddingUsage, TextEmbeddingResult
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel


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

    def get_num_tokens(self, model: str, credentials: dict, texts: list[str]) -> list[int]:
        return [0] * len(texts)
