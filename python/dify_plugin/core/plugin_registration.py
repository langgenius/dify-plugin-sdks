import os
from collections.abc import Mapping
from pathlib import Path
from typing import TypeVar

import werkzeug
import werkzeug.exceptions
from werkzeug import Request
from werkzeug.routing import Map, Rule

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.setup import PluginAsset, PluginConfiguration
from dify_plugin.core.utils.class_loader import load_multi_subclasses_from_source, load_single_subclass_from_source
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities.agent import AgentStrategyConfiguration, AgentStrategyProviderConfiguration
from dify_plugin.entities.endpoint import EndpointProviderConfiguration
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ModelProviderConfiguration
from dify_plugin.entities.tool import ToolConfiguration, ToolProviderConfiguration
from dify_plugin.interfaces.agent import AgentStrategy
from dify_plugin.interfaces.endpoint import Endpoint
from dify_plugin.interfaces.model import ModelProvider
from dify_plugin.interfaces.model.ai_model import AIModel
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.moderation_model import ModerationModel
from dify_plugin.interfaces.model.rerank_model import RerankModel
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel
from dify_plugin.interfaces.model.tts_model import TTSModel
from dify_plugin.interfaces.tool import Tool, ToolProvider
from dify_plugin.protocol.oauth import OAuthProviderProtocol

T = TypeVar("T")


class PluginRegistration:
    configuration: PluginConfiguration
    tools_configuration: list[ToolProviderConfiguration]
    tools_mapping: dict[
        str,
        tuple[
            ToolProviderConfiguration,
            type[ToolProvider],
            dict[str, tuple[ToolConfiguration, type[Tool]]],
        ],
    ]
    agent_strategies_configuration: list[AgentStrategyProviderConfiguration]
    agent_strategies_mapping: dict[
        str,
        tuple[
            AgentStrategyProviderConfiguration,
            dict[str, tuple[AgentStrategyConfiguration, type[AgentStrategy]]],
        ],
    ]

    models_configuration: list[ModelProviderConfiguration]
    models_mapping: dict[
        str,
        tuple[
            ModelProviderConfiguration,
            ModelProvider,
            dict[ModelType, AIModel],
        ],
    ]
    endpoints_configuration: list[EndpointProviderConfiguration]
    endpoints: Map
    datasource_configuration: list[None]  # TBD
    datasource_mapping: dict[  # provider -> (provider_cls, datasource_mapping)
        str,
        tuple[
            None,
            dict[str, tuple[None, type[None]]],  # datasource_name -> (datasource_configuration, datasource_cls)
        ],
    ]  # TBD

    files: list[PluginAsset]

    def __init__(self, config: DifyPluginEnv) -> None:
        """
        Initialize plugin
        """
        self.tools_configuration = []
        self.models_configuration = []
        self.tools_mapping = {}
        self.models_mapping = {}
        self.endpoints_configuration = []
        self.endpoints = Map()
        self.files = []
        self.agent_strategies_configuration = []
        self.agent_strategies_mapping = {}

        # load plugin configuration
        self._load_plugin_configuration()
        # load plugin class
        self._resolve_plugin_cls()
        # load plugin assets
        self._load_plugin_assets()

    def _load_plugin_assets(self):
        """
        load plugin assets
        """
        # open _assets folder
        with os.scandir("_assets") as entries:
            for entry in entries:
                if entry.is_file():
                    entry_bytes = Path(entry).read_bytes()
                    self.files.append(PluginAsset(filename=entry.name, data=entry_bytes))

    def _load_plugin_configuration(self):
        """
        load basic plugin configuration from manifest.yaml
        """
        try:
            file = load_yaml_file("manifest.yaml")
            self.configuration = PluginConfiguration(**file)

            for provider in self.configuration.plugins.tools:
                fs = load_yaml_file(provider)
                tool_provider_configuration = ToolProviderConfiguration(**fs)
                self.tools_configuration.append(tool_provider_configuration)
            for provider in self.configuration.plugins.models:
                fs = load_yaml_file(provider)
                model_provider_configuration = ModelProviderConfiguration(**fs)
                self.models_configuration.append(model_provider_configuration)
            for provider in self.configuration.plugins.endpoints:
                fs = load_yaml_file(provider)
                endpoint_configuration = EndpointProviderConfiguration(**fs)
                self.endpoints_configuration.append(endpoint_configuration)
            for provider in self.configuration.plugins.agent_strategies:
                fs = load_yaml_file(provider)
                agent_provider_configuration = AgentStrategyProviderConfiguration(**fs)
                self.agent_strategies_configuration.append(agent_provider_configuration)

        except Exception as e:
            raise ValueError(f"Error loading plugin configuration: {e!s}") from e

    def _resolve_tool_providers(self):
        """
        walk through all the tool providers and tools and load the classes from sources
        """
        for provider in self.tools_configuration:
            # load class
            source = provider.extra.python.source
            # remove extension
            module_source = os.path.splitext(source)[0]
            # replace / with .
            module_source = module_source.replace("/", ".")
            cls = load_single_subclass_from_source(
                module_name=module_source,
                script_path=os.path.join(os.getcwd(), source),
                parent_type=ToolProvider,
            )

            # load tools class
            tools = {}
            for tool in provider.tools:
                tool_source = tool.extra.python.source
                tool_module_source = os.path.splitext(tool_source)[0]
                tool_module_source = tool_module_source.replace("/", ".")
                tool_cls = load_single_subclass_from_source(
                    module_name=tool_module_source,
                    script_path=os.path.join(os.getcwd(), tool_source),
                    parent_type=Tool,
                )

                if tool_cls._is_get_runtime_parameters_overridden():
                    tool.has_runtime_parameters = True

                tools[tool.identity.name] = (tool, tool_cls)

            self.tools_mapping[provider.identity.name] = (provider, cls, tools)

    def _resolve_agent_providers(self):
        """
        walk through all the agent providers and strategies and load the classes from sources
        """
        for provider in self.agent_strategies_configuration:
            strategies = {}
            for strategy in provider.strategies:
                strategy_source = strategy.extra.python.source
                strategy_module_source = os.path.splitext(strategy_source)[0]
                strategy_module_source = strategy_module_source.replace("/", ".")
                strategy_cls = load_single_subclass_from_source(
                    module_name=strategy_module_source,
                    script_path=os.path.join(os.getcwd(), strategy_source),
                    parent_type=AgentStrategy,
                )

                strategies[strategy.identity.name] = (strategy, strategy_cls)

            self.agent_strategies_mapping[provider.identity.name] = (provider, strategies)

    def _is_strict_subclass(self, cls: type[T], *parent_cls: type[T]) -> bool:
        """
        check if the class is a strict subclass of one of the parent classes
        """
        return any(issubclass(cls, parent) and cls != parent for parent in parent_cls)

    def _resolve_model_providers(self):
        """
        walk through all the model providers and models and load the classes from sources
        """
        for provider in self.models_configuration:
            # load class
            source = provider.extra.python.provider_source
            # remove extension
            module_source = os.path.splitext(source)[0]
            # replace / with .
            module_source = module_source.replace("/", ".")
            cls = load_single_subclass_from_source(
                module_name=module_source,
                script_path=os.path.join(os.getcwd(), source),
                parent_type=ModelProvider,
            )

            # load models class
            models = {}
            for model_source in provider.extra.python.model_sources:
                model_module_source = os.path.splitext(model_source)[0]
                model_module_source = model_module_source.replace("/", ".")
                model_classes = load_multi_subclasses_from_source(
                    module_name=model_module_source,
                    script_path=os.path.join(os.getcwd(), model_source),
                    parent_type=AIModel,
                )

                for model_cls in model_classes:
                    if self._is_strict_subclass(
                        model_cls,
                        LargeLanguageModel,
                        TextEmbeddingModel,
                        RerankModel,
                        TTSModel,
                        Speech2TextModel,
                        ModerationModel,
                    ):
                        models[model_cls.model_type] = model_cls(provider.models)  # type: ignore

            provider_instance = cls(provider, models)  # type: ignore
            self.models_mapping[provider.provider] = (
                provider,
                provider_instance,
                models,
            )

    def _resolve_endpoints(self):
        """
        load endpoints
        """
        for endpoint_provider in self.endpoints_configuration:
            # load endpoints
            for endpoint in endpoint_provider.endpoints:
                # remove extension
                module_source = os.path.splitext(endpoint.extra.python.source)[0]
                # replace / with .
                module_source = module_source.replace("/", ".")
                endpoint_cls = load_single_subclass_from_source(
                    module_name=module_source,
                    script_path=os.path.join(os.getcwd(), endpoint.extra.python.source),
                    parent_type=Endpoint,
                )

                self.endpoints.add(Rule(endpoint.path, methods=[endpoint.method], endpoint=endpoint_cls))

    def _resolve_plugin_cls(self):
        """
        register all plugin extensions
        """
        # load tool providers and tools
        self._resolve_tool_providers()

        # load model providers and models
        self._resolve_model_providers()

        # load endpoints
        self._resolve_endpoints()

        # load agent providers and strategies
        self._resolve_agent_providers()

    def get_tool_provider_cls(self, provider: str):
        """
        get the tool provider class by provider name
        :param provider: provider name
        :return: tool provider class
        """
        for provider_registration in self.tools_mapping:
            if provider_registration == provider:
                return self.tools_mapping[provider_registration][1]

    def get_tool_cls(self, provider: str, tool: str):
        """
        get the tool class by provider
        :param provider: provider name
        :param tool: tool name
        :return: tool class
        """
        for provider_registration in self.tools_mapping:
            if provider_registration == provider:
                registration = self.tools_mapping[provider_registration][2].get(tool)
                if registration:
                    return registration[1]

    def get_agent_provider_cls(self, provider: str):
        """
        get the agent provider class by provider name
        :param provider: provider name
        :return: agent provider class
        """
        for provider_registration in self.agent_strategies_mapping:
            if provider_registration == provider:
                return self.agent_strategies_mapping[provider_registration][1]

    def get_agent_strategy_cls(self, provider: str, agent: str):
        """
        get the agent class by provider
        :param provider: provider name
        :param agent: agent name
        :return: agent class
        """
        for provider_registration in self.agent_strategies_mapping:
            if provider_registration == provider:
                registration = self.agent_strategies_mapping[provider_registration][1].get(agent)
                if registration:
                    return registration[1]

    def get_model_provider_instance(self, provider: str):
        """
        get the model provider class by provider name
        :param provider: provider name
        :return: model provider class
        """
        for provider_registration in self.models_mapping:
            if provider_registration == provider:
                return self.models_mapping[provider_registration][1]

    def get_model_instance(self, provider: str, model_type: ModelType):
        """
        get the model class by provider
        :param provider: provider name
        :param model: model name
        :return: model class
        """
        for provider_registration in self.models_mapping:
            if provider_registration == provider:
                registration = self.models_mapping[provider_registration][2].get(model_type)
                if registration:
                    return registration

    def get_supported_oauth_provider_cls(self, provider: str) -> type[OAuthProviderProtocol] | None:
        """
        get provider which supports oauth
        :param provider: provider name
        :return: supported oauth providers
        """
        for provider_registration in self.tools_mapping:
            if provider_registration == provider and self.tools_mapping[provider_registration][0].oauth_schema:
                return self.tools_mapping[provider_registration][1]

        return None

    def dispatch_endpoint_request(self, request: Request) -> tuple[type[Endpoint], Mapping]:
        """
        dispatch endpoint request, match the request to the registered endpoints

        returns the endpoint and the values
        """
        adapter = self.endpoints.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return endpoint, values
        except werkzeug.exceptions.HTTPException as e:
            raise ValueError(f"Failed to dispatch endpoint request: {e!s}") from e
