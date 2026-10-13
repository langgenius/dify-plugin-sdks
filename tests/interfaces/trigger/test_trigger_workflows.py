import pytest
from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    Subscription,
    TriggerSubscriptionConstructorRuntime,
)
from dify_plugin.errors.trigger import EventIgnoreError, TriggerValidationError
from dify_plugin.interfaces.trigger import EventRuntime
from dify_plugin.plugin import Plugin
from tests.core.plugin_fixtures import contract_plugin, contract_source

__all__ = ["contract_plugin", "contract_source"]


@pytest.fixture
def session(contract_plugin: Plugin) -> Session:
    return Session(
        session_id="trigger-session",
        executor=contract_plugin.executer,
        reader=contract_plugin.request_reader,
        writer=contract_plugin.default_response_writer,
    )


@pytest.mark.parametrize(
    ("credential_type", "credentials"),
    [
        (CredentialType.API_KEY, {"api_key": "valid"}),
        (CredentialType.OAUTH, {"access_token": "valid"}),
        (CredentialType.UNAUTHORIZED, None),
    ],
)
def test_subscription_dispatch_event_refresh_and_unsubscribe_workflow(
    contract_plugin: Plugin,
    session: Session,
    credential_type: CredentialType,
    credentials: dict | None,
) -> None:
    factory = contract_plugin.registration.trigger_factory
    constructor = factory.get_subscription_constructor(
        "events",
        TriggerSubscriptionConstructorRuntime(
            session=session, credential_type=credential_type, credentials=credentials
        ),
    )
    options = constructor.fetch_parameter_options("event")
    assert [(option.value, option.label.en_us) for option in options] == [
        ("echo", "event")
    ]
    assert constructor.last_credentials == (credentials or {})
    assert constructor.last_credential_type == credential_type
    subscription = constructor.create_subscription(
        endpoint="https://callback.invalid/webhook",
        parameters={"event": options[0].value, "label": "release"},
        credentials=credentials or {},
        credential_type=credential_type,
    )
    assert subscription.endpoint == "https://callback.invalid/webhook"
    assert subscription.properties == {
        "external_id": "subscription",
        "credential_type": credential_type.value,
    }
    assert constructor.last_credentials == (credentials or {})
    provider = factory.get_trigger_provider(
        "events", session, credentials, credential_type
    )
    request = Request.from_values(
        method="POST",
        data='{"message":"hello"}',
        content_type="application/json",
    )
    dispatch = provider.dispatch_event(subscription, request)
    assert dispatch.events == ["echo"]
    assert dispatch.response.status_code == 202
    assert dispatch.response.get_data() == b"accepted"
    assert dispatch.payload == {"message": "hello"}
    event = factory.get_trigger_event_handler(
        "events",
        dispatch.events[0],
        EventRuntime(
            session=session,
            credential_type=credential_type,
            subscription=subscription,
            credentials=credentials,
        ),
    )
    variables = event.on_event(request, subscription.parameters, dispatch.payload)
    assert variables.variables == {
        "payload": {"message": "hello"},
        "parameters": {"event": "echo", "label": "release"},
        "body": '{"message":"hello"}',
    }
    assert event.runtime.subscription is subscription
    assert event.runtime.credentials == credentials
    assert event.fetch_parameter_options("event")[0].value == "echo"
    refreshed = constructor.refresh_subscription(
        subscription, credentials or {}, credential_type
    )
    assert subscription.expires_at == 100
    assert refreshed.expires_at == 200
    assert refreshed.parameters == subscription.parameters
    assert refreshed.properties == subscription.properties
    assert refreshed.endpoint == subscription.endpoint
    assert constructor.last_credentials == (credentials or {})
    assert constructor.last_credential_type == credential_type
    result = constructor.delete_subscription(
        refreshed, credentials or {}, credential_type
    )
    assert result.success
    assert result.message == "subscription"
    assert constructor.last_credentials == (credentials or {})
    assert constructor.last_credential_type == credential_type


def test_webhook_rejection_and_event_filter_reach_caller(
    contract_plugin: Plugin, session: Session
) -> None:
    factory = contract_plugin.registration.trigger_factory
    subscription = Subscription(
        endpoint="https://callback.invalid/", properties={"reject": True}
    )
    provider = factory.get_trigger_provider(
        "events", session, None, CredentialType.UNAUTHORIZED
    )
    request = Request.from_values(method="POST", json={"message": "hello"})
    with pytest.raises(TriggerValidationError, match="invalid webhook"):
        provider.dispatch_event(subscription, request)
    event = factory.get_trigger_event_handler(
        "events",
        "echo",
        EventRuntime(
            session=session,
            credential_type=CredentialType.UNAUTHORIZED,
            subscription=subscription,
        ),
    )
    with pytest.raises(EventIgnoreError, match="event filtered"):
        event.on_event(request, {"ignore": True}, {"message": "hello"})


def test_subscription_api_key_validation_and_failed_unsubscribe(
    contract_plugin: Plugin, session: Session
) -> None:
    constructor = (
        contract_plugin.registration.trigger_factory.get_subscription_constructor(
            "events",
            TriggerSubscriptionConstructorRuntime(
                session=session, credential_type=CredentialType.API_KEY
            ),
        )
    )
    constructor.validate_api_key({"api_key": "valid"})
    with pytest.raises(ValueError, match="invalid credentials"):
        constructor.validate_api_key({"api_key": "invalid"})
    subscription = Subscription(
        endpoint="https://callback.invalid/", properties={"external_id": "subscription"}
    )
    result = constructor.delete_subscription(
        subscription, {"api_key": "invalid"}, CredentialType.API_KEY
    )
    assert not result.success
    assert result.message == "subscription"
