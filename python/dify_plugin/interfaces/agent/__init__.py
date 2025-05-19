import logging
from abc import abstractmethod
from collections.abc import Generator, Mapping
from typing import Any, Optional, Union, final

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from dify_plugin.core.runtime import Session
from dify_plugin.entities.agent import AgentInvokeMessage, AgentRuntime
from dify_plugin.entities.model import AIModelEntity, ModelPropertyKey
from dify_plugin.entities.model.llm import LLMModelConfig, LLMUsage
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageRole,
    PromptMessageTool,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.tool import ToolDescription, ToolIdentity, ToolParameter, ToolProviderType
from dify_plugin.interfaces.tool import ToolLike, ToolProvider


class AgentToolIdentity(ToolIdentity):
    provider: str = Field(..., description="The provider of the tool")


class AgentModelConfig(LLMModelConfig):
    entity: AIModelEntity | None = None
    history_prompt_messages: list[PromptMessage] = Field(default_factory=list)

    @field_validator("history_prompt_messages", mode="before")
    @classmethod
    def convert_prompt_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError("prompt_messages must be a list")

        for i in range(len(v)):
            if v[i]["role"] == PromptMessageRole.USER.value:
                v[i] = UserPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.ASSISTANT.value:
                v[i] = AssistantPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.SYSTEM.value:
                v[i] = SystemPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.TOOL.value:
                v[i] = ToolPromptMessage(**v[i])
            else:
                v[i] = PromptMessage(**v[i])

        return v


class AgentScratchpadUnit(BaseModel):
    """
    Agent First Prompt Entity.
    """

    class Action(BaseModel):
        """
        Action Entity.
        """

        action_name: str
        action_input: Union[dict, str]

        def to_dict(self) -> dict:
            """
            Convert to dictionary.
            """
            return {
                "action": self.action_name,
                "action_input": self.action_input,
            }

    agent_response: Optional[str] = ""
    thought: Optional[str] = ""
    action_str: Optional[str] = ""
    observation: Optional[str] = ""
    action: Optional[Action] = None

    def is_final(self) -> bool:
        """
        Check if the scratchpad unit is final.
        """
        return self.action is not None and self.action.action_name.lower() == "final answer"


class ToolInvokeMeta(BaseModel):
    """
    Tool invoke meta
    """

    time_cost: float = Field(..., description="The time cost of the tool invoke")
    error: Optional[str] = None
    tool_config: Optional[dict] = None

    @classmethod
    def empty(cls) -> "ToolInvokeMeta":
        """
        Get an empty instance of ToolInvokeMeta
        """
        return cls(time_cost=0.0, error=None, tool_config={})

    @classmethod
    def error_instance(cls, error: str) -> "ToolInvokeMeta":
        """
        Get an instance of ToolInvokeMeta with error
        """
        return cls(time_cost=0.0, error=error, tool_config={})

    def to_dict(self) -> dict:
        return {
            "time_cost": self.time_cost,
            "error": self.error,
            "tool_config": self.tool_config,
        }


class ToolEntity(BaseModel):
    identity: AgentToolIdentity
    parameters: list[ToolParameter] = Field(default_factory=list)
    description: Optional[ToolDescription] = None
    output_schema: Optional[dict] = None
    has_runtime_parameters: bool = Field(default=False, description="Whether the tool has runtime parameters")
    # provider type
    provider_type: ToolProviderType = ToolProviderType.BUILT_IN

    # runtime parameters
    runtime_parameters: Mapping[str, Any] = {}
    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    @field_validator("parameters", mode="before")
    @classmethod
    def set_parameters(cls, v, validation_info: ValidationInfo) -> list[ToolParameter]:
        return v or []


class AgentProvider(ToolProvider):
    def validate_credentials(self, credentials: dict):
        """
        Always permit the agent to run
        """
        pass

    def _validate_credentials(self, credentials: dict):
        pass


class AgentStrategy(ToolLike[AgentInvokeMessage]):
    @final
    def __init__(
        self,
        runtime: AgentRuntime,
        session: Session,
    ):
        """
        Initialize the agent strategy

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session
        self.response_type = AgentInvokeMessage

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(self, parameters: dict) -> Generator[AgentInvokeMessage, None, None]:
        pass

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(self, parameters: dict) -> Generator[AgentInvokeMessage, None, None]:
        # convert parameters into correct types
        parameters = self._convert_parameters(parameters)
        return self._invoke(parameters)

    def increase_usage(self, final_llm_usage_dict: dict[str, Optional[LLMUsage]], usage: LLMUsage):
        if not final_llm_usage_dict["usage"]:
            final_llm_usage_dict["usage"] = usage
        else:
            llm_usage = final_llm_usage_dict["usage"]
            llm_usage.prompt_tokens += usage.prompt_tokens
            llm_usage.completion_tokens += usage.completion_tokens
            llm_usage.prompt_price += usage.prompt_price
            llm_usage.completion_price += usage.completion_price
            llm_usage.total_price += usage.total_price
            llm_usage.total_tokens += usage.total_tokens

    def recalc_llm_max_tokens(
        self, model_entity: AIModelEntity, prompt_messages: list[PromptMessage], parameters: dict
    ):
        # recalc max_tokens if sum(prompt_token +  max_tokens) over model token limit

        model_context_tokens = model_entity.model_properties.get(ModelPropertyKey.CONTEXT_SIZE)

        max_tokens = 0
        for parameter_rule in model_entity.parameter_rules:
            if parameter_rule.name == "max_tokens" or (
                parameter_rule.use_template and parameter_rule.use_template == "max_tokens"
            ):
                max_tokens = (
                    parameters.get(parameter_rule.name) or parameters.get(parameter_rule.use_template or "")
                ) or 0

        if model_context_tokens is None:
            return -1

        if max_tokens is None:
            max_tokens = 0

        prompt_tokens = self._get_num_tokens_by_gpt2(prompt_messages)

        if prompt_tokens + max_tokens > model_context_tokens:
            max_tokens = max(model_context_tokens - prompt_tokens, 16)

            for parameter_rule in model_entity.parameter_rules:
                if parameter_rule.name == "max_tokens" or (
                    parameter_rule.use_template and parameter_rule.use_template == "max_tokens"
                ):
                    parameters[parameter_rule.name] = max_tokens

    def _get_num_tokens_by_gpt2(self, prompt_messges: list[PromptMessage]) -> int:
        """
        Get number of tokens for given prompt messages by gpt2
        Some provider models do not provide an interface for obtaining the number of tokens.
        Here, the gpt2 tokenizer is used to calculate the number of tokens.
        This method can be executed offline, and the gpt2 tokenizer has been cached in the project.

        :param text: plain text of prompt. You need to convert the original message to plain text
        :return: number of tokens
        """
        import tiktoken

        text = " ".join([prompt.content for prompt in prompt_messges if isinstance(prompt.content, str)])
        return len(tiktoken.encoding_for_model("gpt2").encode(text))

    def _init_prompt_tools(self, tools: list[ToolEntity] | None) -> list[PromptMessageTool]:
        """
        Init tools
        """

        prompt_messages_tools = []
        for tool in tools or []:
            try:
                prompt_tool = self._convert_tool_to_prompt_message_tool(tool)
            except Exception:
                # api tool may be deleted
                logging.exception("Failed to convert tool to prompt message tool")
                continue

            # save prompt tool
            prompt_messages_tools.append(prompt_tool)

        return prompt_messages_tools

    def _convert_tool_to_prompt_message_tool(self, tool: ToolEntity) -> PromptMessageTool:
        """
        convert tool to prompt message tool
        """
        message_tool = PromptMessageTool(
            name=tool.identity.name,
            description=tool.description.llm if tool.description else "",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        parameters = tool.parameters
        for parameter in parameters:
            if parameter.form != ToolParameter.ToolParameterForm.LLM:
                continue

            parameter_type = parameter.type
            if parameter.type in {
                ToolParameter.ToolParameterType.FILE,
                ToolParameter.ToolParameterType.FILES,
            }:
                continue
            if parameter.type in {
                ToolParameter.ToolParameterType.SELECT,
                ToolParameter.ToolParameterType.SECRET_INPUT,
            }:
                parameter_type = ToolParameter.ToolParameterType.STRING
            enum = []
            if parameter.type == ToolParameter.ToolParameterType.SELECT:
                enum = [option.value for option in parameter.options] if parameter.options else []

            message_tool.parameters["properties"][parameter.name] = {
                "type": parameter_type,
                "description": parameter.llm_description or "",
            }

            if len(enum) > 0:
                message_tool.parameters["properties"][parameter.name]["enum"] = enum

            if parameter.required:
                message_tool.parameters["required"].append(parameter.name)

        return message_tool

    def update_prompt_message_tool(self, tool: ToolEntity, prompt_tool: PromptMessageTool) -> PromptMessageTool:
        """
        update prompt message tool
        """
        # try to get tool runtime parameters
        tool_runtime_parameters = tool.parameters

        for parameter in tool_runtime_parameters:
            if parameter.form != ToolParameter.ToolParameterForm.LLM:
                continue

            parameter_type = parameter.type
            if parameter.type in {
                ToolParameter.ToolParameterType.FILE,
                ToolParameter.ToolParameterType.FILES,
            }:
                continue
            if parameter.type in {
                ToolParameter.ToolParameterType.SELECT,
                ToolParameter.ToolParameterType.SECRET_INPUT,
            }:
                parameter_type = ToolParameter.ToolParameterType.STRING
            enum = []
            if parameter.type == ToolParameter.ToolParameterType.SELECT:
                enum = [option.value for option in parameter.options] if parameter.options else []

            prompt_tool.parameters["properties"][parameter.name] = {
                "type": parameter_type,
                "description": parameter.llm_description or "",
            }

            if len(enum) > 0:
                prompt_tool.parameters["properties"][parameter.name]["enum"] = enum

            if parameter.required and parameter.name not in prompt_tool.parameters["required"]:
                prompt_tool.parameters["required"].append(parameter.name)

        return prompt_tool
