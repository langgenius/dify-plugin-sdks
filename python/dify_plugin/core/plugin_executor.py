import binascii
import tempfile
from collections.abc import Generator, Iterable, Mapping
from typing import Any

from werkzeug import Request, Response

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.request import (
    AgentInvokeRequest,
    DatasourceCrawlWebsiteRequest,
    DatasourceGetPageContentRequest,
    DatasourceGetPagesRequest,
    DatasourceOnlineDriveBrowseFilesRequest,
    DatasourceOnlineDriveDownloadFileRequest,
    DatasourceValidateCredentialsRequest,
    DynamicParameterFetchParameterOptionsRequest,
    EndpointInvokeRequest,
    ModelGetAIModelSchemas,
    ModelGetLLMNumTokens,
    ModelGetTextEmbeddingNumTokens,
    ModelGetTTSVoices,
    ModelInvokeLLMRequest,
    ModelInvokeModerationRequest,
    ModelInvokeMultimodalEmbeddingRequest,
    ModelInvokeMultimodalRerankRequest,
    ModelInvokeRerankRequest,
    ModelInvokeSpeech2TextRequest,
    ModelInvokeTextEmbeddingRequest,
    ModelInvokeTTSRequest,
    ModelValidateModelCredentialsRequest,
    ModelValidateProviderCredentialsRequest,
    OAuthGetAuthorizationUrlRequest,
    OAuthGetCredentialsRequest,
    OAuthRefreshCredentialsRequest,
    ToolGetRuntimeParametersRequest,
    ToolInvokeRequest,
    ToolValidateCredentialsRequest,
    TriggerDispatchEventRequest,
    TriggerDispatchResponse,
    TriggerInvokeEventRequest,
    TriggerInvokeEventResponse,
    TriggerRefreshRequest,
    TriggerRefreshResponse,
    TriggerSubscribeRequest,
    TriggerSubscriptionResponse,
    TriggerUnsubscribeRequest,
    TriggerUnsubscribeResponse,
    TriggerValidateProviderCredentialsRequest,
)
from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.core.runtime import Session
from dify_plugin.core.utils.http_parser import deserialize_request, serialize_response
from dify_plugin.entities import ParameterOption
from dify_plugin.entities.agent import AgentRuntime
from dify_plugin.entities.datasource import (
    DatasourceRuntime,
)
from dify_plugin.entities.oauth import OAuthCredentials
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.tool import ToolRuntime
from dify_plugin.entities.trigger import (
    EventDispatch,
    Subscription,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
    Variables,
)
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.datasource import DatasourceProvider
from dify_plugin.interfaces.endpoint import Endpoint
from dify_plugin.interfaces.model.ai_model import AIModel
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.moderation_model import ModerationModel
from dify_plugin.interfaces.model.rerank_model import RerankModel
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from dify_plugin.interfaces.model.tts_model import TTSModel
from dify_plugin.interfaces.tool import Tool
from dify_plugin.interfaces.trigger import Event, EventRuntime, Trigger, TriggerSubscriptionConstructor
from dify_plugin.protocol.dynamic_select import DynamicSelectProtocol
from dify_plugin.protocol.oauth import OAuthProviderProtocol


class PluginExecutor:
    def __init__(self, config: DifyPluginEnv, registration: PluginRegistration) -> None:
        self.config = config
        self.registration = registration

    def validate_tool_provider_credentials(self, session: Session, data: ToolValidateCredentialsRequest):
        provider_instance = self.registration.get_tool_provider_cls(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        provider_instance = provider_instance()
        provider_instance.validate_credentials(data.credentials)

        return {"result": True}

    def invoke_tool(self, session: Session, request: ToolInvokeRequest):
        provider_cls = self.registration.get_tool_provider_cls(request.provider)
        if provider_cls is None:
            raise ValueError(f"Provider `{request.provider}` not found")

        tool_cls = self.registration.get_tool_cls(request.provider, request.tool)
        if tool_cls is None:
            raise ValueError(f"Tool `{request.tool}` not found for provider `{request.provider}`")

        # instantiate tool
        tool = tool_cls(
            runtime=ToolRuntime(
                credentials=request.credentials,
                credential_type=request.credential_type,
                user_id=request.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        # invoke tool
        yield from tool.invoke(request.tool_parameters)

    def invoke_agent_strategy(self, session: Session, request: AgentInvokeRequest):
        agent_cls = self.registration.get_agent_strategy_cls(request.agent_strategy_provider, request.agent_strategy)
        if agent_cls is None:
            raise ValueError(
                f"Agent `{request.agent_strategy}` not found for provider `{request.agent_strategy_provider}`"
            )

        agent = agent_cls(
            runtime=AgentRuntime(
                user_id=request.user_id,
            ),
            session=session,
        )
        yield from agent.invoke(request.agent_strategy_params)

    def get_tool_runtime_parameters(self, session: Session, data: ToolGetRuntimeParametersRequest):
        tool_cls = self.registration.get_tool_cls(data.provider, data.tool)
        if tool_cls is None:
            raise ValueError(f"Tool `{data.tool}` not found for provider `{data.provider}`")

        if not tool_cls._is_get_runtime_parameters_overridden():
            raise ValueError(f"Tool `{data.tool}` does not implement runtime parameters")

        tool_instance = tool_cls(
            runtime=ToolRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        return {
            "parameters": tool_instance.get_runtime_parameters(),
        }

    def validate_model_provider_credentials(self, session: Session, data: ModelValidateProviderCredentialsRequest):
        provider_instance = self.registration.get_model_provider_instance(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        provider_instance.validate_provider_credentials(data.credentials)

        return {"result": True, "credentials": data.credentials}

    def validate_model_credentials(self, session: Session, data: ModelValidateModelCredentialsRequest):
        provider_instance = self.registration.get_model_provider_instance(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if model_instance is None:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

        model_instance.validate_credentials(data.model, data.credentials)

        return {"result": True, "credentials": data.credentials}

    def invoke_llm(self, session: Session, data: ModelInvokeLLMRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, LargeLanguageModel):
            return model_instance.invoke(
                data.model,
                data.credentials,
                data.prompt_messages,
                data.model_parameters,
                data.tools,
                data.stop,
                data.stream,
                data.user_id,
            )
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def get_llm_num_tokens(self, session: Session, data: ModelGetLLMNumTokens):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)

        if isinstance(model_instance, LargeLanguageModel):
            return {
                "num_tokens": model_instance.get_num_tokens(
                    data.model,
                    data.credentials,
                    data.prompt_messages,
                    data.tools,
                )
            }
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_text_embedding(self, session: Session, data: ModelInvokeTextEmbeddingRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, TextEmbeddingModel):
            return model_instance.invoke(
                data.model,
                data.credentials,
                data.texts,
                data.user_id,
            )
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_multimodal_embedding(self, session: Session, data: ModelInvokeMultimodalEmbeddingRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, TextEmbeddingModel):
            return model_instance.invoke_multimodal(
                data.model,
                data.credentials,
                data.documents,
                user=data.user_id,
                input_type=data.input_type,
            )
        raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def get_text_embedding_num_tokens(self, session: Session, data: ModelGetTextEmbeddingNumTokens):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, TextEmbeddingModel):
            return {
                "num_tokens": model_instance.get_num_tokens(
                    data.model,
                    data.credentials,
                    data.texts,
                )
            }
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_rerank(self, session: Session, data: ModelInvokeRerankRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, RerankModel):
            return model_instance.invoke(
                data.model,
                data.credentials,
                data.query,
                data.docs,
                data.score_threshold,
                data.top_n,
                data.user_id,
            )
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_multimodal_rerank(self, session: Session, data: ModelInvokeMultimodalRerankRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, RerankModel):
            return model_instance.invoke_multimodal(
                data.model,
                data.credentials,
                data.query,
                data.docs,
                score_threshold=data.score_threshold,
                top_n=data.top_n,
                user=data.user_id,
            )
        raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_tts(self, session: Session, data: ModelInvokeTTSRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, TTSModel):
            b = model_instance.invoke(
                data.model,
                data.tenant_id,
                data.credentials,
                data.content_text,
                data.voice,
                data.user_id,
            )
            if isinstance(b, bytes | bytearray | memoryview):
                yield {"result": binascii.hexlify(b).decode()}
                return

            for chunk in b:
                yield {"result": binascii.hexlify(chunk).decode()}
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def get_tts_model_voices(self, session: Session, data: ModelGetTTSVoices):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, TTSModel):
            return {"voices": model_instance.get_tts_model_voices(data.model, data.credentials, data.language)}
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_speech_to_text(self, session: Session, data: ModelInvokeSpeech2TextRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)

        with tempfile.NamedTemporaryFile(suffix=".mp3", mode="wb", delete=True) as temp:
            temp.write(binascii.unhexlify(data.file))
            temp.flush()

            with open(temp.name, "rb") as f:
                if isinstance(model_instance, Speech2TextModel):
                    return {
                        "result": model_instance.invoke(
                            data.model,
                            data.credentials,
                            f,
                            data.user_id,
                        )
                    }
                else:
                    raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def get_ai_model_schemas(self, session: Session, data: ModelGetAIModelSchemas):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)
        if isinstance(model_instance, AIModel):
            return {"model_schema": model_instance.get_model_schema(data.model, data.credentials)}
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_moderation(self, session: Session, data: ModelInvokeModerationRequest):
        model_instance = self.registration.get_model_instance(data.provider, data.model_type)

        if isinstance(model_instance, ModerationModel):
            return {
                "result": model_instance.invoke(
                    data.model,
                    data.credentials,
                    data.text,
                    data.user_id,
                )
            }
        else:
            raise ValueError(f"Model `{data.model_type}` not found for provider `{data.provider}`")

    def invoke_endpoint(self, session: Session, data: EndpointInvokeRequest):
        bytes_data = binascii.unhexlify(data.raw_http_request)
        request = deserialize_request(bytes_data)

        try:
            # dispatch request
            endpoint, values = self.registration.dispatch_endpoint_request(request)
            # construct response
            endpoint_instance: Endpoint = endpoint(session)
            response = endpoint_instance.invoke(request, values, data.settings)
        except ValueError as e:
            response = Response(str(e), status=404)
        except Exception as e:
            response = Response(f"Internal Server Error: {e!s}", status=500)

        # check if response is a generator
        if isinstance(response.response, Generator):
            # return headers
            yield {
                "status": response.status_code,
                "headers": dict(response.headers.items()),
            }

            for chunk in response.response:
                if isinstance(chunk, bytes | bytearray | memoryview):
                    yield {"result": binascii.hexlify(chunk).decode()}
                else:
                    yield {"result": binascii.hexlify(chunk.encode("utf-8")).decode()}
        else:
            result = {
                "status": response.status_code,
                "headers": dict(response.headers.items()),
            }

            if isinstance(response.response, bytes | bytearray | memoryview):
                result["result"] = binascii.hexlify(response.response).decode()
            elif isinstance(response.response, str):
                result["result"] = binascii.hexlify(response.response.encode("utf-8")).decode()
            elif isinstance(response.response, Iterable):
                result["result"] = ""
                for chunk in response.response:
                    if isinstance(chunk, bytes | bytearray | memoryview):
                        result["result"] += binascii.hexlify(chunk).decode()
                    else:
                        result["result"] += binascii.hexlify(chunk.encode("utf-8")).decode()

            yield result

    def _get_oauth_provider_instance(self, session: Session, provider: str) -> OAuthProviderProtocol:
        oauth_supported_provider: OAuthProviderProtocol | None = self.registration.get_supported_oauth_provider(
            session=session,
            provider=provider,
        )
        if oauth_supported_provider is None:
            raise ValueError(f"Provider `{provider}` does not support OAuth")

        return oauth_supported_provider

    def get_oauth_authorization_url(self, session: Session, data: OAuthGetAuthorizationUrlRequest) -> Mapping[str, str]:
        provider_instance: OAuthProviderProtocol = self._get_oauth_provider_instance(
            session=session, provider=data.provider
        )

        return {
            "authorization_url": provider_instance.oauth_get_authorization_url(
                redirect_uri=data.redirect_uri, system_credentials=data.system_credentials
            ),
        }

    def get_oauth_credentials(self, session: Session, data: OAuthGetCredentialsRequest) -> Mapping[str, Any]:
        provider_instance: OAuthProviderProtocol = self._get_oauth_provider_instance(
            session=session, provider=data.provider
        )
        bytes_data: bytes = binascii.unhexlify(data.raw_http_request)
        request: Request = deserialize_request(bytes_data)

        credentials: OAuthCredentials = provider_instance.oauth_get_credentials(
            redirect_uri=data.redirect_uri, system_credentials=data.system_credentials, request=request
        )

        return {
            "metadata": credentials.metadata or {},
            "credentials": credentials.credentials,
            "expires_at": credentials.expires_at,
        }

    def refresh_oauth_credentials(
        self, session: Session, data: OAuthRefreshCredentialsRequest
    ) -> dict[str, Mapping[str, Any] | int]:
        provider_instance: OAuthProviderProtocol = self._get_oauth_provider_instance(
            session=session, provider=data.provider
        )
        credentials: OAuthCredentials = provider_instance.oauth_refresh_credentials(
            redirect_uri=data.redirect_uri, system_credentials=data.system_credentials, credentials=data.credentials
        )

        return {
            "credentials": credentials.credentials,
            "expires_at": credentials.expires_at,
        }

    def validate_datasource_credentials(
        self, session: Session, data: DatasourceValidateCredentialsRequest
    ) -> dict[str, bool]:
        provider_instance_cls: type[DatasourceProvider] = self.registration.get_datasource_provider_cls(
            provider=data.provider
        )
        provider_instance = provider_instance_cls()
        provider_instance.validate_credentials(credentials=data.credentials)

        return {
            "result": True,
        }

    def _get_dynamic_parameter_action(
        self, session: Session, data: DynamicParameterFetchParameterOptionsRequest
    ) -> DynamicSelectProtocol | None:
        """
        get the dynamic parameter provider class by provider name

        :param session: session
        :param data: data
        :return: dynamic parameter provider class
        """
        if data.provider_action and data.provider_action == "provider":
            trigger_provider: TriggerSubscriptionConstructor = self.registration.get_trigger_subscription_constructor(
                provider_name=data.provider,
                runtime=TriggerSubscriptionConstructorRuntime(
                    session=session,
                    credentials=data.credentials,
                    credential_type=data.credential_type,
                ),
            )
            return trigger_provider

        trigger_event: Event | None = self.registration.try_get_trigger_event_handler(
            provider_name=data.provider,
            event=data.provider_action,
            runtime=EventRuntime(
                session=session,
                credential_type=data.credential_type,
                credentials=data.credentials or {},
                subscription=Subscription(
                    expires_at=-1,
                    endpoint="NO_SUBSCRIPTION",
                    properties={},
                ),
            ),
        )
        if trigger_event is not None:
            return trigger_event

        # get tool
        tool_cls: type[Tool] | None = self.registration.get_tool_cls(provider=data.provider, tool=data.provider_action)
        if tool_cls is not None:
            return tool_cls(
                runtime=ToolRuntime(credentials=data.credentials, user_id=data.user_id, session_id=session.session_id),
                session=session,
            )
        raise ValueError("Cannot find the target to fetch parameter options")

    def invoke_trigger_event(self, session: Session, request: TriggerInvokeEventRequest) -> TriggerInvokeEventResponse:
        """
        Invoke trigger event
        """
        event: Event = self.registration.get_trigger_event_handler(
            provider_name=request.provider,
            event=request.event,
            runtime=EventRuntime(
                session=session,
                credential_type=request.credential_type,
                credentials=request.credentials or {},
                subscription=request.subscription,
            ),
        )
        try:
            variables: Variables = event.on_event(
                request=deserialize_request(raw_data=binascii.unhexlify(request.raw_http_request)),
                parameters=request.parameters,
                payload=request.payload,
            )
            return TriggerInvokeEventResponse(
                variables=variables.variables,
                cancelled=False,
            )
        except EventIgnoreError:
            return TriggerInvokeEventResponse(
                variables={},
                cancelled=True,
            )
        except Exception as e:
            raise e

    def validate_trigger_provider_credentials(
        self, session: Session, request: TriggerValidateProviderCredentialsRequest
    ):
        """
        Validate trigger provider credentials
        """
        runtime = TriggerSubscriptionConstructorRuntime(
            session=session,
            credentials=request.credentials,
            credential_type=CredentialType.API_KEY,
        )

        provider_instance: TriggerSubscriptionConstructor = self.registration.get_trigger_subscription_constructor(
            provider_name=request.provider, runtime=runtime
        )
        provider_instance.validate_api_key(credentials=request.credentials)
        return {"result": True}

    def dispatch_trigger_event(self, session: Session, request: TriggerDispatchEventRequest) -> TriggerDispatchResponse:
        """
        Dispatch trigger event
        """
        trigger_provider_instance: Trigger = self.registration.get_trigger_provider(
            provider_name=request.provider,
            session=session,
            credentials=request.credentials,
            credential_type=request.credential_type,
        )
        subscription: Subscription = request.subscription
        original_request: Request = deserialize_request(raw_data=binascii.unhexlify(request.raw_http_request))
        dispatch_result: EventDispatch = trigger_provider_instance.dispatch_event(
            subscription=subscription, request=original_request
        )
        return TriggerDispatchResponse(
            user_id=dispatch_result.user_id,
            events=dispatch_result.events,
            response=binascii.hexlify(data=serialize_response(response=dispatch_result.response)).decode(),
            payload=dispatch_result.payload,
        )

    def subscribe_trigger(self, session: Session, request: TriggerSubscribeRequest) -> TriggerSubscriptionResponse:
        """
        Subscribe to a trigger with the external service
        """
        trigger_provider_instance: TriggerSubscriptionConstructor = (
            self.registration.get_trigger_subscription_constructor(
                provider_name=request.provider,
                runtime=TriggerSubscriptionConstructorRuntime(
                    session=session,
                    credentials=request.credentials,
                    credential_type=request.credential_type,
                ),
            )
        )

        subscription: Subscription = trigger_provider_instance.create_subscription(
            endpoint=request.endpoint,
            parameters=request.parameters,
            credentials=request.credentials,
            credential_type=request.credential_type,
        )
        return TriggerSubscriptionResponse(subscription=subscription.model_dump())

    def unsubscribe_trigger(self, session: Session, request: TriggerUnsubscribeRequest) -> TriggerUnsubscribeResponse:
        """
        Unsubscribe from a trigger subscription
        """
        trigger_subscription_constructor_instance: TriggerSubscriptionConstructor = (
            self.registration.get_trigger_subscription_constructor(
                provider_name=request.provider,
                runtime=TriggerSubscriptionConstructorRuntime(
                    session=session,
                    credentials=request.credentials,
                    credential_type=request.credential_type,
                ),
            )
        )

        unsubscription: UnsubscribeResult = trigger_subscription_constructor_instance.delete_subscription(
            subscription=request.subscription, credentials=request.credentials, credential_type=request.credential_type
        )
        return TriggerUnsubscribeResponse(subscription=unsubscription.model_dump())

    def refresh_trigger(self, session: Session, request: TriggerRefreshRequest) -> TriggerRefreshResponse:
        """
        Refresh/extend an existing trigger subscription without changing configuration
        """
        trigger_subscription_constructor_instance: TriggerSubscriptionConstructor = (
            self.registration.get_trigger_subscription_constructor(
                provider_name=request.provider,
                runtime=TriggerSubscriptionConstructorRuntime(
                    session=session,
                    credentials=request.credentials,
                    credential_type=request.credential_type,
                ),
            )
        )
        return TriggerRefreshResponse(
            subscription=trigger_subscription_constructor_instance.refresh_subscription(
                subscription=request.subscription,
                credentials=request.credentials,
                credential_type=request.credential_type,
            ).model_dump()
        )

    def fetch_parameter_options(
        self, session: Session, data: DynamicParameterFetchParameterOptionsRequest
    ) -> dict[str, list[ParameterOption]]:
        action_instance: DynamicSelectProtocol | None = self._get_dynamic_parameter_action(session=session, data=data)
        assert action_instance, f"Provider `{data.provider}` not found"
        return {
            "options": action_instance.fetch_parameter_options(parameter=data.parameter),
        }

    def datasource_crawl_website(self, session: Session, data: DatasourceCrawlWebsiteRequest):
        datasource_cls = self.registration.get_website_crawl_datasource_cls(data.provider, data.datasource)
        datasource_instance = datasource_cls(
            runtime=DatasourceRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        return datasource_instance.website_crawl(data.datasource_parameters)

    def datasource_get_pages(self, session: Session, data: DatasourceGetPagesRequest):
        datasource_cls = self.registration.get_online_document_datasource_cls(data.provider, data.datasource)
        datasource_instance = datasource_cls(
            runtime=DatasourceRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        yield datasource_instance.get_pages(data.datasource_parameters)

    def datasource_get_page_content(self, session: Session, data: DatasourceGetPageContentRequest):
        datasource_cls = self.registration.get_online_document_datasource_cls(data.provider, data.datasource)
        datasource_instance = datasource_cls(
            runtime=DatasourceRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        return datasource_instance.get_content(page=data.page)

    def datasource_online_drive_browse_files(self, session: Session, data: DatasourceOnlineDriveBrowseFilesRequest):
        datasource_cls = self.registration.get_online_drive_datasource_cls(data.provider, data.datasource)
        datasource_instance = datasource_cls(
            runtime=DatasourceRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        yield datasource_instance.browse_files(data.request)

    def datasource_online_drive_download_file(self, session: Session, data: DatasourceOnlineDriveDownloadFileRequest):
        datasource_cls = self.registration.get_online_drive_datasource_cls(data.provider, data.datasource)
        datasource_instance = datasource_cls(
            runtime=DatasourceRuntime(
                credentials=data.credentials,
                user_id=data.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        return datasource_instance.download_file(data.request)
