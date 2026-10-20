import pytest
from pytest_mock import MockerFixture

from dify_plugin.entities.credential import CredentialCheckResult
from dify_plugin.entities.oauth import OAuthRevokeResult, OAuthSchema
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.plugin import Plugin

from .plugin_fixtures import contract_plugin, contract_source, invoke

__all__ = ["contract_plugin", "contract_source"]

CHECK_RESULTS = [
    None,
    CredentialCheckResult(status="valid", reason_code=None, retryable=False),
    CredentialCheckResult(
        status="invalid", reason_code="credential_expired", retryable=False
    ),
    CredentialCheckResult(
        status="temporarily_unavailable",
        reason_code="provider_timeout",
        retryable=True,
    ),
    CredentialCheckResult(status="unsupported", reason_code=None, retryable=False),
]


@pytest.mark.parametrize("detailed", [False, True])
@pytest.mark.parametrize("result", CHECK_RESULTS)
def test_validation_result_compatibility(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    detailed: bool,
    result: CredentialCheckResult | None,
) -> None:
    provider = contract_plugin.registration.get_tool_provider_cls("contract")
    check = mocker.patch.object(provider, "_validate_credentials", return_value=result)
    request = {
        "type": "tool",
        "action": "validate_tool_credentials",
        "provider": "contract",
        "user_id": "user",
        "credentials": {"access_tokens": "token"},
    }
    if detailed:
        request.update(result_format="detailed", credential_type="oauth2")
    messages = invoke(contract_plugin, request)
    check.assert_called_once_with(request["credentials"])
    if detailed:
        expected = (
            result.model_dump()
            if result is not None
            else {"status": "valid", "reason_code": None, "retryable": False}
        )
        assert messages == [{"type": "stream", "data": expected}]
    elif result is None or result.status == "valid":
        assert messages == [{"type": "stream", "data": {"result": True}}]
    else:
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert (
            messages[0]["data"]["error_type"] == "ToolProviderCredentialValidationError"
        )
        assert messages[0]["data"]["message"] == (result.reason_code or result.status)


@pytest.mark.parametrize("detailed", [False, True])
@pytest.mark.parametrize(
    "error",
    [
        ToolProviderCredentialValidationError("provider request failed"),
        NotImplementedError("validation is not implemented"),
        RuntimeError("provider bug"),
    ],
)
def test_validation_preserves_exception_types(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    detailed: bool,
    error: Exception,
) -> None:
    provider = contract_plugin.registration.get_tool_provider_cls("contract")
    mocker.patch.object(provider, "_validate_credentials", side_effect=error)
    request = {
        "type": "tool",
        "action": "validate_tool_credentials",
        "provider": "contract",
        "user_id": "user",
        "credentials": {},
    }
    if detailed:
        request.update(result_format="detailed", credential_type="api_key")
    messages = invoke(contract_plugin, request)
    assert len(messages) == 1
    assert messages[0]["type"] == "error"
    assert messages[0]["data"]["error_type"] == type(error).__name__
    assert messages[0]["data"]["message"] == str(error)


@pytest.mark.parametrize(
    "fields",
    [
        {"result_format": "detailed"},
        {"result_format": "detailed", "credential_type": "unauthorized"},
        {"result_format": "unknown", "credential_type": "api_key"},
    ],
)
def test_invalid_check_request_does_not_call_provider(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    fields: dict,
) -> None:
    provider = contract_plugin.registration.get_tool_provider_cls("contract")
    check = mocker.spy(provider, "_validate_credentials")
    messages = invoke(
        contract_plugin,
        {
            "type": "tool",
            "action": "validate_tool_credentials",
            "provider": "contract",
            "user_id": "user",
            "credentials": {},
            **fields,
        },
    )
    check.assert_not_called()
    assert len(messages) == 1
    assert messages[0]["data"]["error_type"] == "ValidationError"


@pytest.mark.parametrize("provider", ["contract", "website"])
@pytest.mark.parametrize(
    "result",
    [
        None,
        OAuthRevokeResult(status="revoked", reason_code=None, retryable=False),
        OAuthRevokeResult(status="unsupported", reason_code=None, retryable=False),
        OAuthRevokeResult(
            status="temporarily_unavailable",
            reason_code="provider_rate_limited",
            retryable=True,
        ),
        OAuthRevokeResult(status="failed", reason_code=None, retryable=False),
    ],
)
def test_revoke_dispatch_and_missing_implementation(
    contract_plugin: Plugin,
    mocker: MockerFixture,
    provider: str,
    result: OAuthRevokeResult | None,
) -> None:
    registration = contract_plugin.registration
    if provider == "contract":
        configuration, provider_cls, _ = registration.tools_mapping[provider]
        configuration.oauth_schema = OAuthSchema()
    else:
        provider_cls = registration.datasource_mapping[provider].provider_cls
    hook = (
        mocker.patch.object(
            provider_cls, "_oauth_revoke_credentials", return_value=result
        )
        if result is not None
        else mocker.spy(provider_cls, "_oauth_revoke_credentials")
    )
    system_credentials = {"client_id": "client", "client_secret": "secret"}
    credentials = {"access_tokens": "token", "refresh_token": "refresh"}
    messages = invoke(
        contract_plugin,
        {
            "type": "oauth",
            "action": "revoke_credentials",
            "provider": provider,
            "user_id": "user",
            "system_credentials": system_credentials,
            "credentials": credentials,
        },
    )
    hook.assert_called_once()
    assert hook.call_args.args[-2:] == (system_credentials, credentials)
    if result is None:
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert messages[0]["data"]["error_type"] == "NotImplementedError"
    else:
        assert messages == [{"type": "stream", "data": result.model_dump()}]
