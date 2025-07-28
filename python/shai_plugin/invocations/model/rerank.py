from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation
from shai_plugin.entities.model.rerank import RerankModelConfig, RerankResult


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
