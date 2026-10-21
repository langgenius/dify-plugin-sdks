from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import (
    ProviderEntity,
)
from dify_plugin.interfaces.model import ModelProvider
from dify_plugin.interfaces.model.ai_model import AIModel, InvokeError

from .utils import prepare_model_factory


class MockModelProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: dict) -> None:
        pass


class MockModel(AIModel):
    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        pass


def test_model_provider_get_model_instance_delegates_to_factory() -> None:
    """
    Ensure ModelProvider.get_model_instance forwards to ModelFactory.get_instance.
    Constructor usage mirrors test_construct_tool.py style: inline subclass
    with minimal init.
    """
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})

    provider_schema = ProviderEntity(
        provider="test",
        label=I18nObject(en_us="test"),
        supported_model_types=[ModelType.LLM],
        configurate_methods=[],
    )

    provider = MockModelProvider(
        provider_schemas=provider_schema, model_factory=model_factory
    )
    result = provider.get_model_instance(ModelType.LLM)
    assert isinstance(result, MockModel)


def test_model_provider_get_model_instance_get_multiple_instances() -> None:
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})

    provider = MockModelProvider(
        provider_schemas=ProviderEntity(
            provider="test",
            label=I18nObject(en_us="test"),
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


def test_model_provider_instances_are_independent_during_concurrent_use() -> None:
    model_factory = prepare_model_factory({ModelType.LLM: MockModel})
    rendezvous = Barrier(4)

    def task(_: int) -> MockModel:
        model = model_factory.get_instance(ModelType.LLM)
        assert isinstance(model, MockModel)
        with model.timing_context():
            rendezvous.wait(timeout=5)
            assert model.started_at > 0
        return model

    with ThreadPoolExecutor(max_workers=4) as executor:
        models = list(executor.map(task, range(4)))

    assert len({id(model) for model in models}) == 4
    assert all(model.started_at == 0 for model in models)
