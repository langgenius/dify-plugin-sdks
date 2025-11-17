from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dify_plugin.entities.datasource import (
    GetOnlineDocumentPageContentRequest,
    OnlineDriveBrowseFilesRequest,
    OnlineDriveDownloadFileRequest,
)
from dify_plugin.entities.model import EmbeddingInputType, ModelType
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageRole,
    PromptMessageTool,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.model.text_embedding import MultiModalContent
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import Subscription


class PluginInvokeType(StrEnum):
    Tool = "tool"
    Model = "model"
    Endpoint = "endpoint"
    Agent = "agent_strategy"
    Trigger = "trigger"
    OAuth = "oauth"
    Datasource = "datasource"
    DynamicParameter = "dynamic_parameter"


class AgentActions(StrEnum):
    InvokeAgentStrategy = "invoke_agent_strategy"


class TriggerActions(StrEnum):
    InvokeTriggerEvent = "invoke_trigger_event"
    ValidateProviderCredentials = "validate_trigger_credentials"
    DispatchTriggerEvent = "dispatch_trigger_event"
    SubscribeTrigger = "subscribe_trigger"
    UnsubscribeTrigger = "unsubscribe_trigger"
    RefreshTrigger = "refresh_trigger"


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
    InvokeMultimodalEmbedding = "invoke_multimodal_embedding"
    GetTextEmbeddingNumTokens = "get_text_embedding_num_tokens"
    InvokeRerank = "invoke_rerank"
    InvokeMultimodalRerank = "invoke_multimodal_rerank"
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
    RefreshCredentials = "refresh_credentials"


class DatasourceActions(StrEnum):
    ValidateCredentials = "validate_datasource_credentials"
    InvokeWebsiteDatasourceGetCrawl = "invoke_website_datasource_get_crawl"
    InvokeOnlineDocumentDatasourceGetPages = "invoke_online_document_datasource_get_pages"
    InvokeOnlineDocumentDatasourceGetPageContent = "invoke_online_document_datasource_get_page_content"
    InvokeOnlineDriveBrowseFiles = "invoke_online_drive_browse_files"
    InvokeOnlineDriveDownloadFile = "invoke_online_drive_download_file"


class DynamicParameterActions(StrEnum):
    FetchParameterOptions = "fetch_parameter_options"


# merge all the access actions
PluginAccessAction = (
    AgentActions
    | TriggerActions
    | ToolActions
    | ModelActions
    | EndpointActions
    | DynamicParameterActions
    | DatasourceActions
)


class PluginAccessRequest(BaseModel):
    type: PluginInvokeType
    user_id: str


class ToolInvokeRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Tool
    action: ToolActions = ToolActions.InvokeTool
    provider: str
    tool: str
    credentials: dict
    credential_type: CredentialType = CredentialType.API_KEY
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
    stop: list[str] | None
    tools: list[PromptMessageTool] | None
    stream: bool = True

    model_config = ConfigDict(protected_namespaces=())


class ModelGetLLMNumTokens(PluginAccessModelRequest, PromptMessageMixin):
    action: ModelActions = ModelActions.GetLLMNumTokens

    tools: list[PromptMessageTool] | None


class ModelInvokeTextEmbeddingRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeTextEmbedding

    texts: list[str]


class ModelInvokeMultimodalEmbeddingRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeMultimodalEmbedding
    model_type: ModelType = ModelType.TEXT_EMBEDDING

    documents: list[MultiModalContent]
    input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT


class ModelGetTextEmbeddingNumTokens(PluginAccessModelRequest):
    action: ModelActions = ModelActions.GetTextEmbeddingNumTokens

    texts: list[str]


class ModelInvokeRerankRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeRerank

    query: str
    docs: list[str]
    score_threshold: float | None
    top_n: int | None


class ModelInvokeMultimodalRerankRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeMultimodalRerank
    model_type: ModelType = ModelType.RERANK

    query: MultiModalContent
    docs: Sequence[MultiModalContent]
    score_threshold: float | None
    top_n: int | None


class ModelInvokeTTSRequest(PluginAccessModelRequest):
    action: ModelActions = ModelActions.InvokeTTS

    content_text: str
    voice: str
    tenant_id: str


class ModelGetTTSVoices(PluginAccessModelRequest):
    action: ModelActions = ModelActions.GetTTSVoices

    language: str | None


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


class OAuthGetAuthorizationUrlRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.OAuth
    action: OAuthActions = OAuthActions.GetAuthorizationUrl
    provider: str
    redirect_uri: str
    system_credentials: Mapping[str, Any]


class OAuthGetCredentialsRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.OAuth
    action: OAuthActions = OAuthActions.GetCredentials
    provider: str
    redirect_uri: str
    system_credentials: Mapping[str, Any]
    raw_http_request: str


class OAuthRefreshCredentialsRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.OAuth
    action: OAuthActions = OAuthActions.RefreshCredentials
    provider: str
    redirect_uri: str
    system_credentials: Mapping[str, Any]
    credentials: Mapping[str, Any]


class DynamicParameterFetchParameterOptionsRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.DynamicParameter
    action: DynamicParameterActions = DynamicParameterActions.FetchParameterOptions
    credentials: dict[str, Any]
    credential_type: CredentialType = CredentialType.UNAUTHORIZED
    provider: str
    provider_action: str
    user_id: str
    parameter: str

    model_config = ConfigDict(protected_namespaces=())


class DatasourceValidateCredentialsRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.ValidateCredentials
    provider: str
    credentials: Mapping[str, Any]


class DatasourceCrawlWebsiteRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.InvokeWebsiteDatasourceGetCrawl
    provider: str
    datasource: str
    credentials: Mapping[str, Any]
    datasource_parameters: Mapping[str, Any]


class DatasourceGetPagesRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.InvokeOnlineDocumentDatasourceGetPages
    provider: str
    datasource: str
    credentials: Mapping[str, Any]
    datasource_parameters: Mapping[str, Any]


class DatasourceGetPageContentRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.InvokeOnlineDocumentDatasourceGetPageContent
    provider: str
    datasource: str
    credentials: Mapping[str, Any]
    page: GetOnlineDocumentPageContentRequest


class DatasourceOnlineDriveBrowseFilesRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.InvokeOnlineDriveBrowseFiles
    provider: str
    datasource: str
    credentials: Mapping[str, Any]
    request: OnlineDriveBrowseFilesRequest


class DatasourceOnlineDriveDownloadFileRequest(PluginAccessRequest):
    type: PluginInvokeType = PluginInvokeType.Datasource
    action: DatasourceActions = DatasourceActions.InvokeOnlineDriveDownloadFile
    provider: str
    datasource: str
    credentials: Mapping[str, Any]
    request: OnlineDriveDownloadFileRequest


class TriggerInvokeEventRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.InvokeTriggerEvent
    provider: str
    event: str
    credentials: Mapping[str, Any]
    credential_type: CredentialType = CredentialType.API_KEY
    subscription: Subscription
    user_id: str
    raw_http_request: str
    parameters: Mapping[str, Any]
    payload: Mapping[str, Any] = Field(
        default_factory=dict,
        description="The decoded payload from the webhook request, which will be delivered into `_on_event` method.",
    )

    model_config = ConfigDict(protected_namespaces=())


class TriggerInvokeEventResponse(BaseModel):
    variables: Mapping[str, Any] = Field(
        description="The output variables of the event, same with the schema defined in `output_schema` in the YAML",
    )
    cancelled: bool = Field(
        default=False,
        description="Whether the event is cancelled.",
    )
    model_config = ConfigDict(protected_namespaces=())


class TriggerValidateProviderCredentialsRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.ValidateProviderCredentials
    provider: str
    credentials: Mapping[str, Any]
    user_id: str

    model_config = ConfigDict(protected_namespaces=())


class TriggerDispatchEventRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.DispatchTriggerEvent
    provider: str
    subscription: Subscription
    credentials: Mapping[str, Any] | None
    credential_type: CredentialType | None
    raw_http_request: str
    user_id: str

    model_config = ConfigDict(protected_namespaces=())


class TriggerDispatchResponse(BaseModel):
    user_id: str = Field(description="The user who triggered the event (e.g. google user ID)")
    events: list[str] = Field(description="List of Event names that should be invoked.")
    response: str = Field(
        description="The HTTP Response object returned to third-party calls. For example, webhook calls, etc."
    )
    payload: Mapping[str, Any] = Field(
        default_factory=dict,
        description="Decoded payload from the webhook request, which will be delivered into `_on_event` method.",
    )

    model_config = ConfigDict(protected_namespaces=())


class TriggerSubscribeRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.SubscribeTrigger
    provider: str
    credentials: Mapping[str, Any]
    credential_type: CredentialType
    endpoint: str
    parameters: Mapping[str, Any]
    user_id: str

    model_config = ConfigDict(protected_namespaces=())


class TriggerSubscriptionResponse(BaseModel):
    subscription: Mapping[str, Any]

    model_config = ConfigDict(protected_namespaces=())


class TriggerUnsubscribeRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.UnsubscribeTrigger
    provider: str
    subscription: Subscription
    credential_type: CredentialType
    credentials: Mapping[str, Any]  # From credentials_schema
    user_id: str

    model_config = ConfigDict(protected_namespaces=())


class TriggerUnsubscribeResponse(BaseModel):
    subscription: Mapping[str, Any]

    model_config = ConfigDict(protected_namespaces=())


class TriggerRefreshRequest(BaseModel):
    type: PluginInvokeType = PluginInvokeType.Trigger
    action: TriggerActions = TriggerActions.RefreshTrigger
    provider: str
    subscription: Subscription
    credential_type: CredentialType
    credentials: Mapping[str, Any]  # From credentials_schema
    user_id: str

    model_config = ConfigDict(protected_namespaces=())


class TriggerRefreshResponse(BaseModel):
    subscription: Mapping[str, Any]

    model_config = ConfigDict(protected_namespaces=())
