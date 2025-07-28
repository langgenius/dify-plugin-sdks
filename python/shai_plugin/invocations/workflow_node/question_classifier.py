from shai_plugin.core.entities.invocation import InvokeType
from shai_plugin.core.runtime import BackwardsInvocation
from shai_plugin.entities.workflow_node import ClassConfig, ModelConfig, NodeResponse


class QuestionClassifierNodeInvocation(BackwardsInvocation[NodeResponse]):
    def invoke(
        self,
        classes: list[ClassConfig],
        model: ModelConfig,
        query: str,
        instruction: str = "",
    ) -> NodeResponse:
        """
        Invoke Question Classifier Node
        """
        response = self._backwards_invoke(
            InvokeType.NodeQuestionClassifier,
            NodeResponse,
            {
                "classes": classes,
                "model": model,
                "query": query,
                "instruction": instruction,
            },
        )

        for data in response:
            return data

        raise Exception("No response from workflow node question classifier")
