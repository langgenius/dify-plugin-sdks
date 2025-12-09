from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation
from dify_plugin.entities.model.rerank import (
    MultiModalRerankModelConfig,
    MultiModalRerankResult,
    RerankModelConfig,
    RerankResult,
)
from dify_plugin.entities.model.text_embedding import MultiModalContent


class RerankInvocation(BackwardsInvocation[RerankResult]):
    def invoke(self, model_config: RerankModelConfig, docs: list[str], query: str) -> RerankResult:
        """
        Invoke rerank
        """
        for data in self._backwards_invoke(
            InvokeType.Rerank,
            RerankResult,
            {
                **model_config.model_dump(),
                "docs": docs,
                "query": query,
            },
        ):
            return data

        raise Exception("No response from rerank")

    def invoke_multimodal(
        self,
        model_config: MultiModalRerankModelConfig,
        query: MultiModalContent,
        docs: list[MultiModalContent],
    ) -> MultiModalRerankResult:
        payload = {
            **model_config.model_dump(),
            "query": query.model_dump() if isinstance(query, MultiModalContent) else query,
            "docs": [doc.model_dump() if isinstance(doc, MultiModalContent) else doc for doc in docs],
        }

        for data in self._backwards_invoke(
            InvokeType.MultimodalRerank,
            MultiModalRerankResult,
            payload,
        ):
            return data

        raise Exception("No response from multimodal rerank")
