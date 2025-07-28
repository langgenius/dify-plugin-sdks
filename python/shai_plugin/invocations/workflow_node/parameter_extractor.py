from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation
from shai_plugin.entities.workflow_node import ModelConfig, NodeResponse, ParameterConfig


class ParameterExtractorNodeInvocation(BackwardsInvocation[NodeResponse]):
    def invoke(
        self,
        parameters: list[ParameterConfig],
        model: ModelConfig,
        query: str,
        instruction: str = "",
    ) -> NodeResponse:
        """
        Invoke Parameter Extractor Node
        """
        response = self._backwards_invoke(
            InvokeType.NodeParameterExtractor,
            NodeResponse,
            {
                "parameters": parameters,
                "model": model,
                "query": query,
                "instruction": instruction,
            },
        )

        for data in response:
            return data

        raise Exception("No response from workflow node parameter extractor")
