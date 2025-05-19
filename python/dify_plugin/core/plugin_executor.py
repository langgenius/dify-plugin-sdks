import binascii
import tempfile
from collections.abc import Generator, Iterable

from werkzeug import Response

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.request import (
    AgentInvokeRequest,
    EndpointInvokeRequest,
    ModelGetAIModelSchemas,
    ModelGetLLMNumTokens,
    ModelGetTextEmbeddingNumTokens,
    ModelGetTTSVoices,
    ModelInvokeLLMRequest,
    ModelInvokeModerationRequest,
    ModelInvokeRerankRequest,
    ModelInvokeSpeech2TextRequest,
    ModelInvokeTextEmbeddingRequest,
    ModelInvokeTTSRequest,
    ModelValidateModelCredentialsRequest,
    ModelValidateProviderCredentialsRequest,
    OAuthGetAuthorizationUrlRequest,
    OAuthGetCredentialsRequest,
    ToolGetRuntimeParametersRequest,
    ToolInvokeRequest,
    ToolValidateCredentialsRequest,
)
from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.core.runtime import Session
from dify_plugin.core.utils.http_parser import parse_raw_request
from dify_plugin.entities.agent import AgentRuntime
from dify_plugin.entities.tool import ToolRuntime
from dify_plugin.interfaces.endpoint import Endpoint
from dify_plugin.interfaces.model.ai_model import AIModel
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.moderation_model import ModerationModel
from dify_plugin.interfaces.model.rerank_model import RerankModel
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from dify_plugin.interfaces.model.tts_model import TTSModel
from dify_plugin.interfaces.tool import ToolProvider
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
        request = parse_raw_request(bytes_data)

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

    def _get_oauth_provider_instance(self, provider: str) -> OAuthProviderProtocol:
        provider_cls = self.registration.get_supported_oauth_provider_cls(provider)
        if provider_cls is None:
            raise ValueError(f"Provider `{provider}` does not support OAuth")

        if provider_cls == ToolProvider:
            return provider_cls()

        raise ValueError(f"Provider `{provider}` does not support OAuth")

    def get_oauth_authorization_url(self, session: Session, data: OAuthGetAuthorizationUrlRequest):
        provider_instance = self._get_oauth_provider_instance(data.provider)

        return {
            "authorization_url": provider_instance.oauth_get_authorization_url(data.system_credentials),
        }

    def get_oauth_credentials(self, session: Session, data: OAuthGetCredentialsRequest):
        provider_instance = self._get_oauth_provider_instance(data.provider)
        bytes_data = binascii.unhexlify(data.raw_http_request)
        request = parse_raw_request(bytes_data)

        return {
            "credentials": provider_instance.oauth_get_credentials(data.system_credentials, request),
        }
