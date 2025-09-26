from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

from werkzeug import Request, Response

from dify_plugin.core.runtime import Session
from dify_plugin.core.trigger_factory import TriggerFactory
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.trigger import (
    Event,
    Subscription,
    TriggerConfiguration,
    TriggerConfigurationExtra,
    TriggerDescription,
    TriggerDispatch,
    TriggerIdentity,
    TriggerParameter,
    TriggerProviderConfiguration,
    TriggerProviderConfigurationExtra,
    TriggerProviderIdentity,
    TriggerSubscriptionConstructorConfiguration,
    TriggerSubscriptionConstructorConfigurationExtra,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
)
from dify_plugin.interfaces.trigger import TriggerEvent, TriggerProvider, TriggerSubscriptionConstructor


class MockTriggerProvider(TriggerProvider):
    """
    Mock Trigger Provider
    """

    def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Dispatch event from webhook
        """
        return TriggerDispatch(
            triggers=["test_event"],
            response=Response("OK", status=200)
        )


class MockTriggerSubscriptionConstructor(TriggerSubscriptionConstructor):
    """
    Mock Trigger Subscription Constructor
    """

    def _validate_api_key(self, credentials: dict):
        """
        Validate API key
        """
        pass

    def _create_subscription(
        self, endpoint: str, credentials: Mapping[str, Any], selected_events: list[str], parameters: Mapping[str, Any]
    ) -> Subscription:
        """
        Create subscription
        """
        return Subscription(
            expires_at=1234567890,
            endpoint=endpoint,
            properties={
                "external_id": "test_external_id",
                "webhook_secret": "test_secret",
            },
            subscribed_events=selected_events,
        )

    def _delete_subscription(self, subscription: Subscription, credentials: Mapping[str, Any]) -> UnsubscribeResult:
        """
        Delete subscription
        """
        return UnsubscribeResult(
            success=True,
            message="Successfully unsubscribed"
        )

    def _refresh(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        """
        Refresh subscription
        """
        return Subscription(
            expires_at=9999999999,
            endpoint=subscription.endpoint,
            properties=subscription.properties,
            subscribed_events=subscription.subscribed_events,
        )

    def _fetch_parameter_options(self, credentials: Mapping[str, Any], parameter: str) -> list[ParameterOption]:
        """
        Fetch parameter options
        """
        return [
            ParameterOption(value="option1", label=I18nObject(en_US="Option 1")),
            ParameterOption(value="option2", label=I18nObject(en_US="Option 2")),
        ]


class MockTriggerEvent(TriggerEvent):
    """
    Mock Trigger Event
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Trigger the event
        """
        return Event(
            variables={
                "test_variable": "test_value",
                "event_data": request.get_data(as_text=True)
            }
        )


def test_trigger_factory_register_and_get_provider():
    """
    Test trigger factory registration and retrieval of provider
    """
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    # Create provider configuration
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_US="Test Provider"),
            description=I18nObject(en_US="Test Provider Description"),
        ),
        credentials_schema=[],
        subscription_constructor=TriggerSubscriptionConstructorConfiguration(
            parameters=[],
            credentials_schema=[],
            extra=TriggerSubscriptionConstructorConfigurationExtra(
                python=TriggerSubscriptionConstructorConfigurationExtra.Python(
                    source="test_constructor.py"
                )
            ),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py")
        ),
    )

    # Create trigger configuration
    trigger_config = TriggerConfiguration(
        identity=TriggerIdentity(
            author="test",
            name="test_event",
            label=I18nObject(en_US="Test Event"),
        ),
        parameters=[
            TriggerParameter(
                name="test_param",
                label=I18nObject(en_US="Test Parameter"),
                type=TriggerParameter.TriggerParameterType.STRING,
            )
        ],
        description=TriggerDescription(
            human=I18nObject(en_US="Human description"),
            llm=I18nObject(en_US="LLM description"),
        ),
        extra=TriggerConfigurationExtra(
            python=TriggerConfigurationExtra.Python(source="test_event.py")
        ),
        output_schema={"test_variable": {"type": "string"}},
    )

    # Register trigger provider with triggers
    registration = factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=MockTriggerSubscriptionConstructor,
        triggers={"test_event": (trigger_config, MockTriggerEvent)},
    )

    # Test getting provider instance
    provider = factory.get_trigger_provider("test_provider", session)
    assert isinstance(provider, MockTriggerProvider)
    assert provider.session == session

    # Test getting provider class
    provider_cls = factory.get_provider_cls("test_provider")
    assert provider_cls == MockTriggerProvider

    # Test getting configuration
    config = factory.get_configuration("test_provider")
    assert config == provider_config


def test_trigger_factory_subscription_constructor():
    """
    Test trigger factory subscription constructor
    """
    factory = TriggerFactory()
    session = MagicMock(spec=Session)
    runtime = TriggerSubscriptionConstructorRuntime(
        credentials={"api_key": "test_key"},
        session_id="test_session"
    )

    # Create provider configuration with subscription constructor
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_US="Test Provider"),
            description=I18nObject(en_US="Test Provider Description"),
        ),
        credentials_schema=[],
        subscription_constructor=TriggerSubscriptionConstructorConfiguration(
            parameters=[],
            credentials_schema=[],
            extra=TriggerSubscriptionConstructorConfigurationExtra(
                python=TriggerSubscriptionConstructorConfigurationExtra.Python(
                    source="test_constructor.py"
                )
            ),
        ),
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py")
        ),
    )

    # Register provider
    factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=MockTriggerSubscriptionConstructor,
        triggers={},
    )

    # Test has_subscription_constructor
    assert factory.has_subscription_constructor("test_provider") is True

    # Test get subscription constructor instance
    constructor = factory.get_subscription_constructor("test_provider", runtime, session)
    assert isinstance(constructor, MockTriggerSubscriptionConstructor)
    assert constructor.runtime == runtime
    assert constructor.session == session

    # Test get subscription constructor class
    constructor_cls = factory.get_subscription_constructor_cls("test_provider")
    assert constructor_cls == MockTriggerSubscriptionConstructor


def test_trigger_factory_trigger_events():
    """
    Test trigger factory trigger event handling
    """
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    # Create configurations
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_US="Test Provider"),
            description=I18nObject(en_US="Test Provider Description"),
        ),
        credentials_schema=[],
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py")
        ),
    )

    trigger_config = TriggerConfiguration(
        identity=TriggerIdentity(
            author="test",
            name="test_event",
            label=I18nObject(en_US="Test Event"),
        ),
        parameters=[],
        description=TriggerDescription(
            human=I18nObject(en_US="Human description"),
            llm=I18nObject(en_US="LLM description"),
        ),
        extra=TriggerConfigurationExtra(
            python=TriggerConfigurationExtra.Python(source="test_event.py")
        ),
    )

    # Register provider with trigger
    registration = factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=None,
        triggers={},
    )

    # Register trigger after provider registration
    registration.register_trigger(
        name="test_event",
        configuration=trigger_config,
        trigger_cls=MockTriggerEvent,
    )

    # Test get trigger event handler
    event_handler = factory.get_trigger_event_handler("test_provider", "test_event", session)
    assert isinstance(event_handler, MockTriggerEvent)
    assert event_handler.session == session

    # Test get trigger configuration
    config = factory.get_trigger_configuration("test_provider", "test_event")
    assert config == trigger_config

    # Test iterate triggers
    triggers = factory.iter_triggers("test_provider")
    assert "test_event" in triggers
    assert triggers["test_event"][0] == trigger_config
    assert triggers["test_event"][1] == MockTriggerEvent


def test_trigger_factory_error_handling():
    """
    Test trigger factory error handling
    """
    factory = TriggerFactory()
    session = MagicMock(spec=Session)

    # Test getting non-existent provider
    try:
        factory.get_trigger_provider("non_existent", session)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Trigger provider `non_existent` not found" in str(e)

    # Create and register a provider
    provider_config = TriggerProviderConfiguration(
        identity=TriggerProviderIdentity(
            author="test",
            name="test_provider",
            label=I18nObject(en_US="Test Provider"),
            description=I18nObject(en_US="Test Provider Description"),
        ),
        credentials_schema=[],
        extra=TriggerProviderConfigurationExtra(
            python=TriggerProviderConfigurationExtra.Python(source="test_provider.py")
        ),
    )

    factory.register_trigger_provider(
        configuration=provider_config,
        provider_cls=MockTriggerProvider,
        subscription_constructor_cls=None,
        triggers={},
    )

    # Test duplicate registration
    try:
        factory.register_trigger_provider(
            configuration=provider_config,
            provider_cls=MockTriggerProvider,
            subscription_constructor_cls=None,
            triggers={},
        )
        assert False, "Should raise ValueError for duplicate registration"
    except ValueError as e:
        assert "Trigger provider `test_provider` is already registered" in str(e)

    # Test getting non-existent trigger event
    try:
        factory.get_trigger_event_handler("test_provider", "non_existent", session)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Trigger `non_existent` not found in provider `test_provider`" in str(e)

    # Test getting subscription constructor when none exists
    runtime = TriggerSubscriptionConstructorRuntime(
        credentials={"api_key": "test_key"},
        session_id="test_session"
    )
    try:
        factory.get_subscription_constructor("test_provider", runtime, session)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Trigger provider `test_provider` does not define a subscription constructor" in str(e)