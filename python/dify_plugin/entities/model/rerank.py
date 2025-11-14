from pydantic import BaseModel, ConfigDict, Field

from dify_plugin.entities.model import BaseModelConfig, ModelType


class RerankDocument(BaseModel):
    """
    Model class for rerank document.
    """

    index: int
    text: str
    score: float


class RerankResult(BaseModel):
    """
    Model class for rerank result.
    """

    model: str
    docs: list[RerankDocument]


class RerankModelConfig(BaseModelConfig):
    """
    Model class for rerank model config.
    """

    model_type: ModelType = ModelType.RERANK
    score_threshold: float
    top_n: int

    model_config = ConfigDict(protected_namespaces=())


class MultiModalRerankResult(BaseModel):
    """Rerank response produced by a multimodal rerank model."""

    model: str = Field(..., description="Identifier of the model producing the reranked documents.")
    docs: list[RerankDocument] = Field(..., description="Reranked documents with scores.")


class MultiModalRerankModelConfig(BaseModelConfig):
    """Configuration payload for invoking a multimodal rerank model."""

    model_type: ModelType = ModelType.RERANK
    score_threshold: float | None = Field(
        default=None,
        description="Optional threshold for filtering documents based on score.",
    )
    top_n: int | None = Field(
        default=None,
        description="Optional limit on the number of documents returned.",
    )

    model_config = ConfigDict(protected_namespaces=())
