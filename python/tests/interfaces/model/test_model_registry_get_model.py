from unittest.mock import MagicMock

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ProviderEntity
from dify_plugin.interfaces.model import ModelProvider


def test_model_provider_get_model_instance_delegates_to_factory():
    """
    Ensure ModelProvider.get_model_instance forwards to ModelFactory.get_instance.
    Constructor usage mirrors test_construct_tool.py style (inline subclass, minimal init).
    """

    class MockModelProvider(ModelProvider):
        def validate_provider_credentials(self, credentials: dict) -> None:
            pass

    provider_schema = ProviderEntity(
        provider="test",
        label=I18nObject(en_US="test"),
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    model_factory = MagicMock(spec=ModelFactory)
    expected_instance = object()
    model_factory.get_instance.return_value = expected_instance

    provider = MockModelProvider(provider_schemas=provider_schema, model_factory=model_factory)

    result = provider.get_model_instance(ModelType.LLM)
    assert result is expected_instance
    model_factory.get_instance.assert_called_once_with(ModelType.LLM)
