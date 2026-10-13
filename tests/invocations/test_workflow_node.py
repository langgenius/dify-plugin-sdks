import pytest

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.entities.workflow_node import (
    ClassConfig,
    ModelConfig,
    NodeResponse,
    ParameterConfig,
)
from dify_plugin.invocations.workflow_node.parameter_extractor import (
    ParameterExtractorNodeInvocation,
)
from dify_plugin.invocations.workflow_node.question_classifier import (
    QuestionClassifierNodeInvocation,
)
from tests.invocations.conftest import RecordInvocation


@pytest.mark.parametrize("node", ["parameter_extractor", "question_classifier"])
def test_workflow_node_serializes_nested_configuration_and_preserves_outputs(
    record_invocation: RecordInvocation, node: str
) -> None:
    model = ModelConfig(
        provider="provider", name="model", completion_params={"temperature": 0}
    )
    response = {
        "process_data": {"model": "resolved-model"},
        "inputs": {"query": "question"},
        "outputs": {"answer": 0, "matched": False, "items": []},
    }
    if node == "parameter_extractor":
        invocation = ParameterExtractorNodeInvocation()
        configuration = [
            ParameterConfig(
                name="answer", type="number", description="Extract", required=False
            )
        ]
        key = "parameters"
        serialized = [
            {
                "name": "answer",
                "type": "number",
                "options": [],
                "description": "Extract",
                "required": False,
            }
        ]
        invoke_type = InvokeType.NodeParameterExtractor
    else:
        invocation = QuestionClassifierNodeInvocation()
        configuration = [ClassConfig(id="0", name="Other")]
        key, serialized = "classes", [{"id": "0", "name": "Other"}]
        invoke_type = InvokeType.NodeQuestionClassifier
    recorded = record_invocation(invocation, [response])

    result = invocation.invoke(configuration, model, "question")

    assert result == NodeResponse(**response)
    assert recorded.requests == [
        (
            invoke_type,
            NodeResponse,
            {
                key: serialized,
                "model": {
                    "provider": "provider",
                    "name": "model",
                    "mode": "chat",
                    "completion_params": {"temperature": 0},
                },
                "query": "question",
                "instruction": "",
            },
        )
    ]
    assert model.completion_params == {"temperature": 0}
    assert recorded.closed


@pytest.mark.parametrize(
    "invocation_type",
    [ParameterExtractorNodeInvocation, QuestionClassifierNodeInvocation],
)
@pytest.mark.parametrize("remote_error", [False, True])
def test_workflow_node_fails_on_missing_or_failed_response(
    record_invocation: RecordInvocation,
    invocation_type: type[
        ParameterExtractorNodeInvocation | QuestionClassifierNodeInvocation
    ],
    remote_error: bool,
) -> None:
    invocation = invocation_type()
    error = RuntimeError("workflow failed")
    recorded = record_invocation(invocation, [error] if remote_error else [])
    model = ModelConfig(provider="provider", name="model")

    with pytest.raises(
        RuntimeError if remote_error else Exception,
        match="workflow failed" if remote_error else "No response",
    ):
        invocation.invoke([], model, "question", instruction="Classify")
    assert recorded.requests[0][2]["instruction"] == "Classify"
    assert recorded.closed
