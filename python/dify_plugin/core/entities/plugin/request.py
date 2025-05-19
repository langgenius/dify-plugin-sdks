from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageRole,
    PromptMessageTool,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)


class PluginInvokeType(StrEnum):
    Tool = "tool"
    Model = "model"
    Endpoint = "endpoint"
    Agent = "agent_strategy"
    OAuth = "oauth"


class AgentActions(StrEnum):
    InvokeAgentStrategy = "invoke_agent_strategy"


class ToolActions(StrEnum):
    ValidateCredentials = "validate_tool_credentials"
    InvokeTool = "invoke_tool"
    GetToolRuntimeParameters = "get_tool_runtime_parameters"


class ModelActions(StrEnum):
    ValidateProviderCredentials = "validate_provider_credentials"
    ValidateModelCredentials = "validate_model_credentials"
    InvokeLLM = "invoke_llm"
    GetLLMNumTokens = "get_llm_num_tokens"
    InvokeTextEmbedding = "invoke_text_embedding"
    GetTextEmbeddingNumTokens = "get_text_embedding_num_tokens"
    InvokeRerank = "invoke_rerank"
    InvokeTTS = "invoke_tts"
    GetTTSVoices = "get_tts_model_voices"
    InvokeSpeech2Text = "invoke_speech2text"
    InvokeModeration = "invoke_moderation"
    GetAIModelSchemas = "get_ai_model_schemas"


class EndpointActions(StrEnum):
    InvokeEndpoint = "invoke_endpoint"


class OAuthActions(StrEnum):
    GetAuthorizationUrl = "get_authorization_url"
    GetCredentials = "get_credentials"


# merge all the access actions
PluginAccessAction = AgentActions | ToolActions | ModelActions | EndpointActions


class PluginAccessRequest(BaseModel):
    type: PluginInvokeType
    user_id: str


class ToolInvokeRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Tool
    action: ToolActions = ToolActions.InvokeTool
    provider: str
    tool: str
    credentials: dict
    tool_parameters: dict[str, Any]


class AgentInvokeRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Agent
    action: AgentActions = AgentActions.InvokeAgentStrategy
    agent_strategy_provider: str
    agent_strategy: str
    agent_strategy_params: dict[str, Any]


class ToolValidateCredentialsRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Tool
    action: ToolActions = ToolActions.ValidateCredentials
    provider: str
    credentials: dict


class ToolGetRuntimeParametersRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Tool
    action: ToolActions = ToolActions.GetToolRuntimeParameters
    provider: str
    tool: str
    credentials: dict


class PluginAccessModelRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Model
    user_id: str
    provider: str
    model_type: ModelType
    model: str
    credentials: dict

    model_config = ConfigDict(protected_namespaces=())


class PromptMessageMixin(BaseModel):
    prompt_messages: list[PromptMessage]

    @field_validator("prompt_messages", mode="before")
    @classmethod
    def convert_prompt_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError("prompt_messages must be a list")

        for i in range(len(v)):
            if isinstance(v[i], PromptMessage):
                continue

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


class ModelInvokeLLMRequest(PluginAccessModelRequest, PromptMessageMixin):
    action: ModelActions = ModelActions.InvokeLLM

    model_parameters: dict[str, Any]
    stop: Optional[list[str]]
    tools: Optional[list[PromptMessageTool]]
    stream: bool = True

    model_config = ConfigDict(protected_namespaces=())


class ModelGetLLMNumTokens(PluginAccessModelRequest, PromptMessageMixin):
    action: ModelActions = ModelActions.GetLLMNumTokens

    tools: Optional[list[PromptMessageTool]]


class ModelInvokeTextEmbeddingRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeTextEmbedding

    texts: list[str]


class ModelGetTextEmbeddingNumTokens(PluginAccessModelRequest):
    action: ModelActions = ModelActions.GetTextEmbeddingNumTokens

    texts: list[str]


class ModelInvokeRerankRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeRerank

    query: str
    docs: list[str]
    score_threshold: Optional[float]
    top_n: Optional[int]


class ModelInvokeTTSRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeTTS

    content_text: str
    voice: str
    tenant_id: str


class ModelGetTTSVoices(PluginAccessModelRequest):
    action: ModelActions = ModelActions.GetTTSVoices

    language: Optional[str]


class ModelInvokeSpeech2TextRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeSpeech2Text

    file: str


class ModelInvokeModerationRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeModeration

    text: str


class ModelValidateProviderCredentialsRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Model
    user_id: str
    provider: str
    credentials: dict

    action: ModelActions = ModelActions.ValidateProviderCredentials

    model_config = ConfigDict(protected_namespaces=())


class ModelValidateModelCredentialsRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Model
    user_id: str
    provider: str
    model_type: ModelType
    model: str
    credentials: dict

    action: ModelActions = ModelActions.ValidateModelCredentials

    model_config = ConfigDict(protected_namespaces=())


class ModelGetAIModelSchemas(PluginAccessModelRequest):
    action: ModelActions = ModelActions.GetAIModelSchemas


class EndpointInvokeRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Endpoint
    action: EndpointActions = EndpointActions.InvokeEndpoint
    settings: dict
    raw_http_request: str


class OAuthGetAuthorizationUrlRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.OAuth
    action: OAuthActions = OAuthActions.GetAuthorizationUrl
    provider: str
    system_credentials: Mapping[str, Any]


class OAuthGetCredentialsRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.OAuth
    action: OAuthActions = OAuthActions.GetCredentials
    provider: str
    system_credentials: Mapping[str, Any]
    raw_http_request: str
