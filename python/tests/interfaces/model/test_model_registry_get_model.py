import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import (
    ProviderEntity,
)
from dify_plugin.interfaces.model import ModelProvider
from dify_plugin.interfaces.model.ai_model import AIModel, InvokeError
from tests.interfaces.model.utils import prepare_model_factory


class MockModelProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: dict) -> None:
        pass


class MockModel(AIModel):
    def invoke(self) -> float:
        with self.timing_context():
            time.sleep(1)
            return 0.0

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_model_provider_get_model_instance_delegates_to_factory():
    """
    Ensure ModelProvider.get_model_instance forwards to ModelFactory.get_instance.
    Constructor usage mirrors test_construct_tool.py style (inline subclass, minimal init).
    """
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})

    provider_schema = ProviderEntity(
        provider="test",
        label=I18nObject(en_US="test"),
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    provider = MockModelProvider(provider_schemas=provider_schema, model_factory=model_factory)
    result = provider.get_model_instance(ModelType.LLM)
    assert isinstance(result, MockModel)


def test_model_provider_get_model_instance_get_multiple_instances():
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})

    provider = MockModelProvider(
        provider_schemas=ProviderEntity(
            provider="test",
            label=I18nObject(en_US="test"),
            supported_model_types=[ModelType.LLM],
            configurate_methods=[],
        ),
        model_factory=model_factory,
    )

    result1 = provider.get_model_instance(ModelType.LLM)
    assert isinstance(result1, MockModel)

    result2 = provider.get_model_instance(ModelType.LLM)
    assert isinstance(result2, MockModel)

    assert result1 is not result2

    result3 = provider.get_model_instance(ModelType.LLM)
    assert isinstance(result3, MockModel)

    assert result1 is not result3
    assert result2 is not result3
    assert result2 is not result3


def test_model_provider_get_model_instance_multithread():
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})

    def task(_):
        model = model_factory.get_instance(ModelType.LLM)
        assert isinstance(model, MockModel)
        model.invoke()

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(task, range(10))
