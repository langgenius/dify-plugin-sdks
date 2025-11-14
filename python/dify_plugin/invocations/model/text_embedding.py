from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation
from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.entities.model.text_embedding import (
    MultiModalContent,
    MultiModalEmbeddingModelConfig,
    MultiModalEmbeddingResult,
    TextEmbeddingModelConfig,
    TextEmbeddingResult,
)


class TextEmbeddingInvocation(BackwardsInvocation[TextEmbeddingResult]):
    def invoke(
        self,
        model_config: TextEmbeddingModelConfig,
        texts: list[str],
        input_type: EmbeddingInputType = EmbeddingInputType.QUERY,
    ) -> TextEmbeddingResult:
        """
        Invoke text embedding
        """
        for data in self._backwards_invoke(
            InvokeType.TextEmbedding,
            TextEmbeddingResult,
            {
                **model_config.model_dump(),
                "texts": texts,
                "input_type": input_type.value,
            },
        ):
            return data

        raise Exception("No response from text embedding")

    def invoke_multimodal(
        self,
        model_config: MultiModalEmbeddingModelConfig,
        documents: list[MultiModalContent],
        input_type: EmbeddingInputType = EmbeddingInputType.QUERY,
    ) -> MultiModalEmbeddingResult:
        payload = {
            **model_config.model_dump(),
            "documents": [
                document.model_dump() if isinstance(document, MultiModalContent) else document for document in documents
            ],
            "input_type": input_type.value,
        }

        for data in self._backwards_invoke(
            InvokeType.MultimodalEmbedding,
            MultiModalEmbeddingResult,
            payload,
        ):
            return data

        raise Exception("No response from multimodal embedding")
