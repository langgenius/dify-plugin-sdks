"""Tests for the trigger factory runtime registry."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sys
import types

import pytest
from werkzeug import Request

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHON_SRC = PROJECT_ROOT / "python"

for candidate in (str(PROJECT_ROOT), str(PYTHON_SRC)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

# Avoid importing the top-level ``dify_plugin`` package which performs heavy
# initialisation (including gevent monkey patching) that is unnecessary for
# unit tests. Instead we register a lightweight namespace package that points
# at the source directory so submodules can be imported normally.
if "dify_plugin" not in sys.modules:
    dify_plugin_pkg = types.ModuleType("dify_plugin")
    dify_plugin_pkg.__path__ = [str(PYTHON_SRC / "dify_plugin")]
    sys.modules["dify_plugin"] = dify_plugin_pkg

from dify_plugin.core.trigger_factory import TriggerFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.trigger import (
    Event,
    Subscription,
    SubscriptionSchema,
    TriggerConfiguration,
    TriggerConfigurationExtra,
    TriggerDescription,
    TriggerIdentity,
    TriggerProviderConfiguration,
    TriggerProviderConfigurationExtra,
    TriggerProviderIdentity,
    TriggerSubscriptionConstructorConfiguration,
    TriggerSubscriptionConstructorConfigurationExtra,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
)
from dify_plugin.interfaces.trigger import TriggerEvent, TriggerProvider, TriggerSubscriptionConstructor


class DummyProvider(TriggerProvider):
    """Minimal provider implementation used for factory tests."""

    def _dispatch_event(self, subscription: Subscription, request: Request):  # pragma: no cover - unused in tests
        raise NotImplementedError


class DummyConstructor(TriggerSubscriptionConstructor):
    """Minimal constructor implementation for instantiation tests."""

    def _validate_api_key(self, credentials: dict):  # pragma: no cover - unused in tests
        return None

    def _create_subscription(
        self,
        endpoint: str,
        credentials: Mapping[str, object],
        selected_events: list[str],
        parameters: Mapping[str, object],
    ) -> Subscription:  # pragma: no cover - unused in tests
        return Subscription(
            expires_at=0,
            endpoint=endpoint,
            parameters={},
            properties={},
        )

    def _delete_subscription(
        self, subscription: Subscription, credentials: Mapping[str, object]
    ) -> UnsubscribeResult:  # pragma: no cover - unused in tests
        return UnsubscribeResult(success=True)

    def _refresh(
        self, subscription: Subscription, credentials: Mapping[str, object]
    ) -> Subscription:  # pragma: no cover - unused in tests
        return subscription


class DummyTrigger(TriggerEvent):
    """Simple trigger that captures the injected session."""

    def _trigger(self, request: Request, parameters: Mapping[str, object]) -> Event:
        return Event(variables={})


@pytest.fixture
def trigger_configuration() -> TriggerConfiguration:
    return TriggerConfiguration(
        identity=TriggerIdentity(
            author="unit",
            name="dummy-event",
            label=I18nObject(en_US="Dummy Event"),
        ),
        parameters=[],
        description=TriggerDescription(
            human=I18nObject(en_US="Human description"),
            llm=I18nObject(en_US="LLM description"),
        ),
        extra=TriggerConfigurationExtra(
            python=TriggerConfigurationExtra.Python(source="dummy_trigger.py"),
        ),
        output_schema=None,
    )


@pytest.fixture
def provider_configuration() -> TriggerProviderConfiguration:
    return TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="unit",
            name="dummy-provider",
            label=I18nObject(en_US="Dummy Provider"),
            description=I18nObject(en_US="Dummy description"),
        ),
        credentials_schema=[],
        oauth_schema=None,
        subscription_schema=SubscriptionSchema(),
        subscription_constructor=TriggerSubscriptionConstructorConfiguration(
            parameters=[],
            credentials_schema=[],
            oauth_schema=None,
            extra=TriggerSubscriptionConstructorConfigurationExtra(
                python=TriggerSubscriptionConstructorConfigurationExtra.Python(
                    source="dummy_constructor.py"
                ),
            ),
        ),
        triggers=[],
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="dummy_provider.py"),
        ),
    )


def test_register_trigger_provider_and_accessors(
    provider_configuration: TriggerProviderConfiguration,
    trigger_configuration: TriggerConfiguration,
) -> None:
    factory = TriggerFactory()

    factory.register_trigger_provider(
        configuration=provider_configuration,
        provider_cls=DummyProvider,
        subscription_constructor_cls=DummyConstructor,
        triggers={"dummy-event": (trigger_configuration, DummyTrigger)},
    )

    session = object()
    provider = factory.get_trigger_provider("dummy-provider", session)
    assert isinstance(provider, DummyProvider)
    assert provider.session is session

    assert factory.has_subscription_constructor("dummy-provider") is True

    runtime = TriggerSubscriptionConstructorRuntime(credentials={}, session_id="session")
    constructor = factory.get_subscription_constructor("dummy-provider", runtime, session)
    assert isinstance(constructor, DummyConstructor)
    assert constructor.runtime is runtime

    handler = factory.get_trigger_event_handler("dummy-provider", "dummy-event", session)
    assert isinstance(handler, DummyTrigger)
    assert handler.session is session

    config = factory.get_trigger_configuration("dummy-provider", "dummy-event")
    assert config is trigger_configuration

    assert dict(factory.iter_triggers("dummy-provider")) == {"dummy-event": (trigger_configuration, DummyTrigger)}


def test_register_trigger_provider_prevents_duplicate_names(
    provider_configuration: TriggerProviderConfiguration,
    trigger_configuration: TriggerConfiguration,
) -> None:
    factory = TriggerFactory()

    factory.register_trigger_provider(
        configuration=provider_configuration,
        provider_cls=DummyProvider,
        subscription_constructor_cls=None,
        triggers={"dummy-event": (trigger_configuration, DummyTrigger)},
    )

    with pytest.raises(ValueError):
        factory.register_trigger_provider(
            configuration=provider_configuration,
            provider_cls=DummyProvider,
            subscription_constructor_cls=None,
            triggers={},
        )


def test_registration_helper_prevents_duplicate_trigger_names(
    provider_configuration: TriggerProviderConfiguration,
    trigger_configuration: TriggerConfiguration,
) -> None:
    factory = TriggerFactory()

    registration = factory.register_trigger_provider(
        configuration=provider_configuration,
        provider_cls=DummyProvider,
        subscription_constructor_cls=None,
        triggers={"dummy-event": (trigger_configuration, DummyTrigger)},
    )

    with pytest.raises(ValueError):
        registration.register_trigger(
            name="dummy-event",
            configuration=trigger_configuration,
            trigger_cls=DummyTrigger,
        )


def test_iter_triggers_returns_copy(
    provider_configuration: TriggerProviderConfiguration,
    trigger_configuration: TriggerConfiguration,
) -> None:
    factory = TriggerFactory()
    factory.register_trigger_provider(
        configuration=provider_configuration,
        provider_cls=DummyProvider,
        subscription_constructor_cls=None,
        triggers={"dummy-event": (trigger_configuration, DummyTrigger)},
    )

    triggers = factory.iter_triggers("dummy-provider")
    assert triggers == {"dummy-event": (trigger_configuration, DummyTrigger)}

    # Mutating the returned mapping must not affect the factory's internal state.
    triggers["dummy-event"] = (trigger_configuration, DummyTrigger)
    assert factory.iter_triggers("dummy-provider") == {"dummy-event": (trigger_configuration, DummyTrigger)}


def test_get_trigger_event_handler_unknown_event(
    provider_configuration: TriggerProviderConfiguration,
    trigger_configuration: TriggerConfiguration,
) -> None:
    factory = TriggerFactory()
    factory.register_trigger_provider(
        configuration=provider_configuration,
        provider_cls=DummyProvider,
        subscription_constructor_cls=None,
        triggers={"dummy-event": (trigger_configuration, DummyTrigger)},
    )

    with pytest.raises(ValueError):
        factory.get_trigger_event_handler("dummy-provider", "missing", object())


def test_get_entry_unknown_provider_raises() -> None:
    factory = TriggerFactory()

    with pytest.raises(ValueError):
        factory.get_trigger_provider("missing", object())
