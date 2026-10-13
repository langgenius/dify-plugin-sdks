from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest
from werkzeug import Request, Response

from dify_plugin.core.runtime import Session
from dify_plugin.core.trigger_factory import TriggerFactory
from dify_plugin.entities import I18nObject
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    EventConfiguration,
    EventConfigurationExtra,
    EventDispatch,
    EventIdentity,
    EventParameter,
    Subscription,
    TriggerProviderConfiguration,
    TriggerProviderConfigurationExtra,
    TriggerProviderIdentity,
    TriggerSubscriptionConstructorConfiguration,
    TriggerSubscriptionConstructorConfigurationExtra,
    TriggerSubscriptionConstructorRuntime,
    Variables,
)
from dify_plugin.interfaces.trigger import (
    Event,
    EventRuntime,
    Trigger,
)
from tests.fixtures.plugins.contract_plugin.triggers.constructor import (
    ContractConstructor,
)


class MockTriggerProvider(Trigger):
    """Mock Trigger Provider"""

    def _dispatch_event(
        self,
        subscription: Subscription,
        request: Request,
    ) -> EventDispatch:
        """Dispatch event from webhook"""
        del subscription
        del request
        return EventDispatch(events=["test_event"], response=Response("OK", status=200))


class MockEventHandler(Event):
    """Mock Event"""

    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """Transform the webhook request into Variables"""
        del parameters
        del payload
        return Variables(
            variables={
                "test_variable": "test_value",
                "event_data": request.get_data(as_text=True),
            },
        )


def test_trigger_factory_register_and_get_provider() -> None:
    """Test trigger factory registration and retrieval of provider"""
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    # Create provider configuration
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_us="Test Provider"),
            description=I18nObject(en_us="Test Provider Description"),
        ),
        subscription_constructor=TriggerSubscriptionConstructorConfiguration(
            parameters=[],
            credentials_schema=[],
            extra=TriggerSubscriptionConstructorConfigurationExtra(
                python=TriggerSubscriptionConstructorConfigurationExtra.Python(
                    source="test_constructor.py",
                ),
            ),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py"),
        ),
    )

    # Create trigger configuration
    trigger_config = EventConfiguration(
        identity=EventIdentity(
            author="test",
            name="test_event",
            label=I18nObject(en_us="Test Event"),
        ),
        parameters=[
            EventParameter(
                name="test_param",
                label=I18nObject(en_us="Test Parameter"),
                type=EventParameter.EventParameterType.STRING,
            ),
        ],
        description=I18nObject(en_us="Human description"),
        extra=EventConfigurationExtra(
            python=EventConfigurationExtra.Python(source="test_event.py"),
        ),
        output_schema={"test_variable": {"type": "string"}},
    )

    # Register trigger provider with events
    factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=ContractConstructor,
        events={"test_event": (trigger_config, MockEventHandler)},
    )

    # Test getting provider instance
    provider = factory.get_trigger_provider("test_provider", session, None, None)
    assert isinstance(provider, MockTriggerProvider)
    assert provider.runtime.session == session

    # Test getting provider class
    provider_cls = factory.get_provider_cls("test_provider")
    assert provider_cls == MockTriggerProvider

    # Test getting configuration
    config = factory.get_configuration("test_provider")
    assert config == provider_config


def test_trigger_factory_subscription_constructor() -> None:
    """Test trigger factory subscription constructor"""
    factory = TriggerFactory()
    credentials = {"api_key": "valid"}
    runtime = TriggerSubscriptionConstructorRuntime(
        credentials=credentials,
        session=MagicMock(spec=Session),
        credential_type=CredentialType.API_KEY,
    )

    # Create provider configuration with subscription constructor
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_us="Test Provider"),
            description=I18nObject(en_us="Test Provider Description"),
        ),
        subscription_constructor=TriggerSubscriptionConstructorConfiguration(
            parameters=[],
            credentials_schema=[],
            extra=TriggerSubscriptionConstructorConfigurationExtra(
                python=TriggerSubscriptionConstructorConfigurationExtra.Python(
                    source="test_constructor.py",
                ),
            ),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py"),
        ),
    )

    # Register provider
    factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=ContractConstructor,
        events={},
    )

    # Test has_subscription_constructor
    assert factory.has_subscription_constructor("test_provider") is True

    # Test get subscription constructor instance
    constructor = factory.get_subscription_constructor("test_provider", runtime)
    assert isinstance(constructor, ContractConstructor)
    assert constructor.runtime.session == runtime.session

    # Test get subscription constructor class
    constructor_cls = factory.get_subscription_constructor_cls("test_provider")
    assert constructor_cls == ContractConstructor

    constructor.validate_api_key(credentials)
    options = constructor.fetch_parameter_options("event")
    assert [option.value for option in options] == ["echo"]
    subscription = constructor.create_subscription(
        endpoint="https://callback.invalid/webhook",
        parameters={"event": options[0].value},
        credentials=credentials,
        credential_type=runtime.credential_type,
    )
    assert subscription.parameters == {"event": "echo"}
    assert subscription.properties["credential_type"] == "api-key"
    refreshed = constructor.refresh_subscription(
        subscription, credentials, runtime.credential_type
    )
    assert subscription.expires_at == 100
    assert refreshed.expires_at == 200
    assert (
        refreshed.endpoint
        == subscription.endpoint
        == "https://callback.invalid/webhook"
    )
    result = constructor.delete_subscription(
        refreshed, credentials, runtime.credential_type
    )
    assert result.success
    assert result.message == subscription.properties["external_id"]


def test_trigger_factory_trigger_events() -> None:
    """Test trigger factory trigger event handling"""
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    # Create configurations
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_us="Test Provider"),
            description=I18nObject(en_us="Test Provider Description"),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py"),
        ),
    )

    trigger_config = EventConfiguration(
        identity=EventIdentity(
            author="test",
            name="test_event",
            label=I18nObject(en_us="Test Event"),
        ),
        parameters=[],
        description=I18nObject(en_us="Human description"),
        extra=EventConfigurationExtra(
            python=EventConfigurationExtra.Python(source="test_event.py"),
        ),
    )

    # Register provider with events
    registration = factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=None,
        events={},
    )

    # Register trigger after provider registration
    registration.register_trigger(
        name="test_event",
        configuration=trigger_config,
        trigger_cls=MockEventHandler,
    )

    # Test get Event
    event = factory.get_trigger_event_handler(
        "test_provider",
        "test_event",
        EventRuntime(
            session=session,
            credential_type=CredentialType.UNAUTHORIZED,
            subscription=Subscription(
                expires_at=1234567890,
                endpoint="test_endpoint",
                properties={
                    "external_id": "test_external_id",
                    "webhook_secret": "test_secret",
                },
            ),
        ),
    )
    assert isinstance(event, MockEventHandler)
    assert event.runtime.session == session

    # Test get trigger configuration
    config = factory.get_trigger_configuration("test_provider", "test_event")
    assert config == trigger_config

    # Test iterate events
    events = factory.iter_events("test_provider")
    assert "test_event" in events
    assert events["test_event"][0] == trigger_config
    assert events["test_event"][1] == MockEventHandler


def test_trigger_factory_error_handling() -> None:
    """Test trigger factory error handling"""
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    assert (
        factory.get_trigger_event_handler_safely(
            "non_existent", "non_existent", MagicMock(spec=EventRuntime)
        )
        is None
    )

    # Test getting non-existent provider
    with pytest.raises(ValueError, match="Trigger provider `non_existent` not found"):
        factory.get_trigger_provider("non_existent", session, None, None)

    # Create and register a provider
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_us="Test Provider"),
            description=I18nObject(en_us="Test Provider Description"),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py"),
        ),
    )

    factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=None,
        events={},
    )

    # Test duplicate registration
    with pytest.raises(
        ValueError,
        match="Trigger provider `test_provider` is already registered",
    ):
        factory.register_trigger_provider(
            configuration=provider_config,
            provider_cls=MockTriggerProvider,
            subscription_constructor_cls=None,
            events={},
        )

    # Test getting non-existent event
    with pytest.raises(
        ValueError,
        match="Event `non_existent` not found in provider `test_provider`",
    ):
        factory.get_trigger_event_handler("test_provider", "non_existent", session)

    # Test getting subscription constructor when none exists
    runtime = TriggerSubscriptionConstructorRuntime(
        credentials={"api_key": "test_key"},
        session=MagicMock(spec=Session),
        credential_type=CredentialType.API_KEY,
    )
    with pytest.raises(
        ValueError,
        match=(
            "Trigger provider `test_provider` does not define a subscription "
            "constructor"
        ),
    ):
        factory.get_subscription_constructor("test_provider", runtime)
