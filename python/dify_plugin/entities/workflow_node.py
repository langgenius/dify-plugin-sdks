from enum import Enum

from pydantic import BaseModel, Field

from dify_plugin.entities.model.llm import LLMMode


class NodeResponse(BaseModel):
    process_data: dict
    inputs: dict
    outputs: dict


class NodeType(str, Enum):
    """
    Node Types.
    """

    START = "start"
    END = "end"
    ANSWER = "answer"
    LLM = "llm"
    KNOWLEDGE_RETRIEVAL = "knowledge-retrieval"
    IF_ELSE = "if-else"
    CODE = "code"
    TEMPLATE_TRANSFORM = "template-transform"
    QUESTION_CLASSIFIER = "question-classifier"
    HTTP_REQUEST = "http-request"
    TOOL = "tool"
    VARIABLE_AGGREGATOR = "variable-aggregator"
    LOOP = "loop"
    ITERATION = "iteration"
    PARAMETER_EXTRACTOR = "parameter-extractor"
    CONVERSATION_VARIABLE_ASSIGNER = "assigner"

    @classmethod
    def value_of(cls, value: str) -> "NodeType":
        """
        Get value of given node type.

        :param value: node type value
        :return: node type
        """
        for node_type in cls:
            if node_type.value == value:
                return node_type
        raise ValueError(f"invalid node type value {value}")


class ModelConfig(BaseModel):
    """
    Model Config
    """

    provider: str
    name: str
    mode: LLMMode = LLMMode.CHAT
    completion_params: dict | None = None


class ParameterConfig(BaseModel):
    """
    Parameter Config
    """

    name: str
    type: str
    options: list[str] = Field(default_factory=list)
    description: str | None
    required: bool | None


class ClassConfig(BaseModel):
    """
    Class Config
    """

    id: str
    name: str
