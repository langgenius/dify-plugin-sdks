from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from shai_plugin.entities.model import BaseModelConfig, ModelType, ModelUsage


class EmbeddingUsage(ModelUsage):
    """
    Model class for embedding usage.
    """

    tokens: int
    total_tokens: int
    unit_price: Decimal
    price_unit: Decimal
    total_price: Decimal
    currency: str
    latency: float


class TextEmbeddingResult(BaseModel):
    """
    Model class for text embedding result.
    """

    model: str
    embeddings: list[list[float]]
    usage: EmbeddingUsage


class TextEmbeddingModelConfig(BaseModelConfig):
    """
    Model class for text embedding model config.
    """

    model_type: ModelType = ModelType.TEXT_EMBEDDING

    model_config = ConfigDict(protected_namespaces=())
