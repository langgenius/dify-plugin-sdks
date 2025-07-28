from pydantic import BaseModel, ConfigDict

from shai_plugin.entities.model import BaseModelConfig, ModelType


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
