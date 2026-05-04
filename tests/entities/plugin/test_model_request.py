from dify_plugin.core.entities.plugin.request import ModelActions, ModelInvokeTextEmbeddingRequest, PluginInvokeType
from dify_plugin.entities.model import EmbeddingInputType, ModelType


def test_text_embedding_request_accepts_input_type() -> None:
    request = ModelInvokeTextEmbeddingRequest(
        type=PluginInvokeType.Model,
        action=ModelActions.InvokeTextEmbedding,
        user_id="user-id",
        provider="provider",
        model_type=ModelType.TEXT_EMBEDDING,
        model="embedding-model",
        credentials={},
        texts=["query text"],
        input_type=EmbeddingInputType.QUERY,
    )

    assert request.input_type == EmbeddingInputType.QUERY


def test_text_embedding_request_defaults_input_type_to_document() -> None:
    request = ModelInvokeTextEmbeddingRequest(
        type=PluginInvokeType.Model,
        action=ModelActions.InvokeTextEmbedding,
        user_id="user-id",
        provider="provider",
        model_type=ModelType.TEXT_EMBEDDING,
        model="embedding-model",
        credentials={},
        texts=["document text"],
    )

    assert request.input_type == EmbeddingInputType.DOCUMENT
