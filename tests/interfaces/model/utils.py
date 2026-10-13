from collections.abc import Generator, Mapping

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk
from dify_plugin.entities.model.message import PromptMessage, PromptMessageTool
from dify_plugin.entities.model.provider import (
    ModelProviderConfiguration,
    ModelProviderConfigurationExtra,
)
from dify_plugin.errors.model import (
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
)
from dify_plugin.interfaces.model.ai_model import AIModel
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel


class StubLLM(LargeLanguageModel):
    def _invoke(self, **kwargs: object) -> LLMResult | Generator[LLMResultChunk]:
        del kwargs
        raise NotImplementedError

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        del model, credentials, prompt_messages, tools
        return 0

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeConnectionError: [TimeoutError],
            InvokeAuthorizationError: [PermissionError],
            InvokeBadRequestError: [ValueError],
        }


def prepare_model_factory(models: Mapping[ModelType, type[AIModel]]) -> ModelFactory:
    return ModelFactory(
        ModelProviderConfiguration(
            provider="test",
            label=I18nObject(en_us="test"),
            supported_model_types=list(models.keys()),
            configurate_methods=[],
            extra=ModelProviderConfigurationExtra(
                python=ModelProviderConfigurationExtra.Python(
                    provider_source="test",
                    model_sources=[],
                ),
            ),
        ),
        models=dict(models),
    )
