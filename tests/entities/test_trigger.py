from types import MappingProxyType

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


@pytest.mark.parametrize("immutable_field", [None, "label", "ignored"])
def test_subscription_credentials_keep_legacy_shared_yaml_mapping_names(
    immutable_field: str | None,
) -> None:
    credential = {"type": "secret-input", "label": {"en_US": "Token"}}
    if immutable_field == "label":
        credential["label"] = MappingProxyType(credential["label"])
    data = {
        "credentials_schema": {"access_token": credential, "refresh_token": credential}
    }
    if immutable_field == "ignored":
        data["unused"] = MappingProxyType({})

    result = TriggerSubscriptionConstructorConfiguration.model_validate(data)

    assert [item.name for item in result.credentials_schema] == [
        "refresh_token",
        "refresh_token",
    ]
    assert TriggerSubscriptionConstructorConfiguration.model_validate(data) == result


@pytest.mark.parametrize("data", [[], "constructor", 42, MappingProxyType({})])
def test_subscription_constructor_rejects_non_dict_configuration(
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


@pytest.mark.parametrize(("default", "expected"), [(False, 0), (True, 1)])
def test_subscription_manifest_keeps_legacy_numeric_boolean_defaults(
    default: bool,
    expected: int,
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

    serialized = result.model_dump(mode="json")["parameters"][0]["default"]
    assert type(serialized) is int
    assert serialized == expected
