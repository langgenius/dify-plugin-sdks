import pytest
from pydantic import ValidationError

from dify_plugin.entities.trigger import TriggerSubscriptionConstructorConfiguration


@pytest.mark.parametrize("mapping", [False, True])
def test_subscription_credentials_support_repeated_normalization(
    mapping: bool,
) -> None:
    # Twilio declares credentials by name; the contract plugin uses a list.
    credentials = {
        "account_sid": {"type": "text-input", "label": {"en_US": "Account SID"}},
        "auth_token": {"type": "secret-input", "label": {"en_US": "Auth Token"}},
    }
    data = {
        "credentials_schema": credentials
        if mapping
        else [{"name": name, **value} for name, value in credentials.items()],
        "oauth_schema": {
            "client_schema": [
                {
                    "name": "client_id",
                    "type": "secret-input",
                    "label": {"en_US": "Client ID"},
                }
            ]
        },
    }
    first = TriggerSubscriptionConstructorConfiguration.model_validate(data)
    second = TriggerSubscriptionConstructorConfiguration.model_validate(data)

    assert first == second
    assert [credential.name for credential in first.credentials_schema] == [
        "account_sid",
        "auth_token",
    ]
    assert first.oauth_schema.client_schema[0].name == "client_id"


def test_subscription_credentials_do_not_alias_shared_yaml_mapping() -> None:
    credential = {"type": "secret-input", "label": {"en_US": "Token"}}
    data = {
        "credentials_schema": {"access_token": credential, "refresh_token": credential}
    }

    result = TriggerSubscriptionConstructorConfiguration.model_validate(data)

    assert [item.name for item in result.credentials_schema] == [
        "access_token",
        "refresh_token",
    ]


@pytest.mark.parametrize("data", [[], "constructor", 42])
def test_subscription_constructor_rejects_non_mapping_configuration(
    data: object,
) -> None:
    with pytest.raises((TypeError, ValidationError)):
        TriggerSubscriptionConstructorConfiguration.model_validate(data)


@pytest.mark.parametrize("credentials", [None, "access_token", 42])
def test_subscription_constructor_rejects_invalid_credentials_schema(
    credentials: object,
) -> None:
    with pytest.raises((TypeError, ValidationError), match="credentials_schema"):
        TriggerSubscriptionConstructorConfiguration.model_validate({
            "credentials_schema": credentials
        })


@pytest.mark.parametrize(
    "data", [None, {}, {"credentials_schema": {}, "oauth_schema": {}}]
)
def test_subscription_constructor_accepts_no_authentication(data: object) -> None:
    # Discord webhook subscriptions use empty credentials and OAuth schemas.
    result = TriggerSubscriptionConstructorConfiguration.model_validate(data)

    assert result.credentials_schema == []
    assert result.parameters == []
    assert result.oauth_schema is None or result.oauth_schema.client_schema == []


@pytest.mark.parametrize("default", [False, True])
def test_subscription_manifest_preserves_boolean_parameter_default(
    default: bool,
) -> None:
    # Google Calendar declares this as a boolean in its subscription constructor.
    result = TriggerSubscriptionConstructorConfiguration.model_validate({
        "parameters": [
            {
                "name": "enrich_event_details",
                "type": "boolean",
                "default": default,
                "label": {"en_US": "Fetch Full Event Details"},
            }
        ]
    })

    assert result.model_dump(mode="json")["parameters"][0]["default"] is default
