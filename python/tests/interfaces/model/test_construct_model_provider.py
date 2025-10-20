from unittest.mock import MagicMock

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ProviderEntity
from dify_plugin.interfaces.model import ModelProvider


def test_construct_model_provider():
    """
    Ensure ModelProvider constructor is intact and usable.
    This guards against overriding or changing __init__ signature.
    """

    class ProviderImpl(ModelProvider):
        def validate_provider_credentials(self, credentials: dict) -> None:
            pass

    provider_schema = ProviderEntity(
        provider="test",
        label=I18nObject(en_US="test"),
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    model_factory = MagicMock(spec=ModelFactory)

    provider = ProviderImpl(provider_schemas=provider_schema, model_factory=model_factory)

    assert provider is not None
    assert provider.get_provider_schema() == provider_schema
    assert provider.model_factory is model_factory
