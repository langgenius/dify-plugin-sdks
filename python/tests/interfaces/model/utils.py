from collections.abc import Mapping

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ModelProviderConfiguration, ModelProviderConfigurationExtra
from dify_plugin.interfaces.model.ai_model import AIModel


def prepare_model_factory(models: Mapping[ModelType, type[AIModel]]) -> ModelFactory:
    model_factory = ModelFactory(
        ModelProviderConfiguration(
            provider="test",
            label=I18nObject(en_US="test"),
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

    return model_factory
