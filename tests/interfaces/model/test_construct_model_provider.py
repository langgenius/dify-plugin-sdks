from unittest.mock import MagicMock

from dify_plugin.core.model_factory import ModelFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ProviderEntity
from dify_plugin.interfaces.model import ModelProvider


def test_provider_dark_icons_are_preserved() -> None:
    icon_small_dark = I18nObject(en_us="small-dark.svg")
    icon_large_dark = I18nObject(en_us="large-dark.svg")
    provider = ProviderEntity(
        provider="test",
        label=I18nObject(en_us="test"),
        icon_small_dark=icon_small_dark,
        icon_large_dark=icon_large_dark,
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    simple_provider = provider.to_simple_provider()

    assert simple_provider.icon_small_dark == icon_small_dark
    assert simple_provider.icon_large_dark == icon_large_dark


def test_construct_model_provider() -> None:
    """
    Ensure ModelProvider constructor is intact and usable.
    This guards against overriding or changing __init__ signature.
    """

    class ProviderImpl(ModelProvider):
        def validate_provider_credentials(self, credentials: dict) -> None:
            pass

    provider_schema = ProviderEntity(
        provider="test",
        label=I18nObject(en_us="test"),
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    model_factory = MagicMock(spec=ModelFactory)

    provider = ProviderImpl(
        provider_schemas=provider_schema, model_factory=model_factory
    )

    assert provider is not None
    assert provider.get_provider_schema() == provider_schema
    assert provider.model_factory is model_factory
