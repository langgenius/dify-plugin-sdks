from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from dify_plugin.entities.model import BaseModelConfig, ModelType, ModelUsage


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


class MultiModalContentType(StrEnum):
    """Supported content types for multimodal inputs."""

    TEXT = "text"
    IMAGE = "image"


class MultiModalContent(BaseModel):
    """A multimodal content payload provided by the caller."""

    content: str = Field(..., description="The payload content, plain text or base64 encoded file data.")
    content_type: MultiModalContentType = Field(..., description="The modality of the provided content.")


class MultiModalEmbeddingResult(BaseModel):
    """Embedding response produced by a multimodal embedding model."""

    model: str = Field(..., description="Identifier of the model generating embeddings.")
    embeddings: list[list[float]] = Field(..., description="Embedding vectors for provided contents.")
    usage: EmbeddingUsage = Field(..., description="Usage metrics associated with the inference.")


class MultiModalEmbeddingModelConfig(BaseModelConfig):
    """Configuration payload for invoking a multimodal embedding model."""

    model_type: ModelType = ModelType.TEXT_EMBEDDING
    tenant_id: str = Field(..., description="Vendor tenant identifier associated with the dataset.")

    model_config = ConfigDict(protected_namespaces=())
