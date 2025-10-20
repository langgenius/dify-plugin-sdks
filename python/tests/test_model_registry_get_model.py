from collections.abc import Generator, Mapping
from unittest.mock import MagicMock

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk, LLMResultChunkDelta
from dify_plugin.entities.model.message import AssistantPromptMessage, PromptMessage, PromptMessageTool
from dify_plugin.entities.model.provider import (
    ModelProviderConfiguration,
    ModelProviderConfigurationExtra,
    ProviderEntity,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model import ModelProvider
from dify_plugin.interfaces.model.ai_model import AIModel


class MockModelProvider(ModelProvider):
    """
    Mock Model Provider
    """

    def validate_provider_credentials(self, credentials: dict) -> None:
        pass


class MockLLM(AIModel):
    """
    Mock LLM
    """

    model_type = ModelType.LLM

    def invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        """
        Invoke LLM

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """
        yield LLMResultChunk(
            model="test",
            prompt_messages=[],
            delta=LLMResultChunkDelta(
                index=0,
                message=AssistantPromptMessage(content="test"),
            ),
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        """
        Get number of tokens

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param tools: tools
        :return: number of tokens
        """
        return 0

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        """
        Validate model credentials

        :param model: model name
        :param credentials: model credentials
        """
        pass

    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error

        :return: Invoke error mapping
        """
        return {}


def test_model_registry_get_model(monkeypatch):
    """
    Test model registry get model
    """
    config = MagicMock()

    def mock_validate_models(cls: ModelProviderConfiguration, values: dict) -> dict:
        """
        Mock validate models
        """
        return values

    monkeypatch.setattr(ModelProviderConfiguration, "validate_models", mock_validate_models)

    def mock_load_yaml_file(file_name: str) -> dict:
        """
        Mock load yaml file
        """
        return {}

    def mock_resolve_plugin_cls(self: PluginRegistration):
        """
        Mock resolve plugin cls
        """
        # add MockLLM to models_mapping
        provider_configuration = ModelProviderConfiguration(
            provider="test",
            label=I18nObject(zh_Hans="test", en_US="test"),
            models={},  # type: ignore
            supported_model_types=[ModelType.LLM],
            extra=ModelProviderConfigurationExtra(
                python=ModelProviderConfigurationExtra.Python(provider_source="test", model_sources=[])
            ),
            configurate_methods=[],
        )

        self.models_mapping = {
            "test": (
                provider_configuration,
                MockModelProvider(
                    provider_schemas=ProviderEntity(
                        provider="test",
                        label=I18nObject(zh_Hans="test", en_US="test"),
                        supported_model_types=[ModelType.LLM],
                        configurate_methods=[],
                    ),
                    model_factory=ModelFactory(
                        provider=provider_configuration,
                        models={ModelType.LLM: MockLLM},
                    ),
                ),
                ModelFactory(
                    provider=provider_configuration,
                    models={ModelType.LLM: MockLLM},
                ),
            )
        }

    def mock_load_plugin_assets(_):
        """
        Mock load plugin assets
        """
        pass

    monkeypatch.setattr(PluginRegistration, "_load_plugin_configuration", mock_load_yaml_file)
    monkeypatch.setattr(PluginRegistration, "_resolve_plugin_cls", mock_resolve_plugin_cls)
    monkeypatch.setattr(PluginRegistration, "_load_plugin_assets", mock_load_plugin_assets)

    plugin_registration = PluginRegistration(config)

    model = plugin_registration.get_model_instance("test", ModelType.LLM)
    assert isinstance(model, MockLLM)
