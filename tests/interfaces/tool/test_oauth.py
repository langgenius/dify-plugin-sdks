from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from typing import Any

import pytest
from pydantic import ValidationError
from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.datasource import DatasourceOAuthCredentials
from dify_plugin.entities.oauth import (
    OAuthCredentials,
    ToolOAuthCredentials,
    TriggerOAuthCredentials,
)
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    Subscription,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
)
from dify_plugin.errors.tool import ToolProviderOAuthError
from dify_plugin.interfaces.datasource import DatasourceProvider
from dify_plugin.interfaces.tool import ToolProvider
from dify_plugin.interfaces.trigger import TriggerSubscriptionConstructor


class _TriggerConstructor(TriggerSubscriptionConstructor):
    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        del credentials, credential_type
        return Subscription(endpoint=endpoint, parameters=parameters)

    def _delete_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> UnsubscribeResult:
        del subscription, credentials, credential_type
        return UnsubscribeResult(success=True)

    def _refresh_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        del credentials, credential_type
        return subscription


@pytest.fixture(params=["tool", "datasource", "trigger"])
def oauth_provider(
    request: pytest.FixtureRequest,
) -> Generator[ToolProvider | DatasourceProvider | TriggerSubscriptionConstructor]:
    if request.param == "tool":
        yield ToolProvider()
        return
    if request.param == "datasource":
        yield DatasourceProvider()
        return
    reader = StdioRequestReader()
    with ThreadPoolExecutor() as executor:
        session = Session("oauth", executor, reader, StdioResponseWriter())
        try:
            yield _TriggerConstructor(
                TriggerSubscriptionConstructorRuntime(
                    session=session,
                    credential_type=CredentialType.OAUTH,
                    credentials={"access_token": "old-token"},
                )
            )
        finally:
            reader.close()


@pytest.mark.parametrize("expires_at", [None, -1, 0, 2_000_000_000])
@pytest.mark.parametrize("refresh", [False, True])
def test_oauth_public_methods_keep_legacy_credentials_and_expiry(
    oauth_provider: ToolProvider | DatasourceProvider | TriggerSubscriptionConstructor,
    monkeypatch: pytest.MonkeyPatch,
    expires_at: int | None,
    refresh: bool,
) -> None:
    credentials = {"access_token": "new-token", "refresh_token": "new-refresh-token"}
    metadata = {}
    if isinstance(oauth_provider, DatasourceProvider):
        source = DatasourceOAuthCredentials(
            credentials=credentials,
            expires_at=expires_at,
            name="Workspace",
            avatar_url="https://example.test/avatar.png",
        )
        metadata = {"name": source.name, "avatar_url": source.avatar_url}
    elif isinstance(oauth_provider, ToolProvider):
        source = ToolOAuthCredentials(credentials=credentials, expires_at=expires_at)
    elif refresh:
        source = OAuthCredentials(
            credentials=credentials, expires_at=-1 if expires_at is None else expires_at
        )
    else:
        source = TriggerOAuthCredentials(credentials=credentials, expires_at=expires_at)
    source_payload = source.model_dump()

    callback_request = Request.from_values(
        "/callback?code=authorization-code&state=expected-state",
        method="POST",
        data="body",
    )
    redirect_uri = "https://example.test/callback"
    system_credentials = {"client_id": "app", "client_secret": "synthetic-secret"}
    previous_credentials = {
        "access_token": "old-token",
        "refresh_token": "old-refresh-token",
    }
    previous_payload = dict(previous_credentials)
    calls = []

    def get_credentials(
        redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> (
        ToolOAuthCredentials
        | DatasourceOAuthCredentials
        | TriggerOAuthCredentials
        | OAuthCredentials
    ):
        calls.append((redirect_uri, dict(system_credentials), request))
        return source

    def refresh_credentials(
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> (
        ToolOAuthCredentials
        | DatasourceOAuthCredentials
        | TriggerOAuthCredentials
        | OAuthCredentials
    ):
        calls.append((redirect_uri, dict(system_credentials), dict(credentials)))
        return source

    monkeypatch.setattr(oauth_provider, "_oauth_get_credentials", get_credentials)
    monkeypatch.setattr(
        oauth_provider, "_oauth_refresh_credentials", refresh_credentials
    )
    invalid_expiry = expires_at is None and not isinstance(
        oauth_provider, TriggerSubscriptionConstructor
    )
    with (
        pytest.raises(ValidationError, match="expires_at")
        if invalid_expiry
        else nullcontext()
    ):
        if refresh:
            result = oauth_provider.oauth_refresh_credentials(
                redirect_uri, system_credentials, previous_credentials
            )
        else:
            result = oauth_provider.oauth_get_credentials(
                redirect_uri, system_credentials, callback_request
            )

        expected_expiry = expires_at
        if expires_at is None or (
            isinstance(oauth_provider, TriggerSubscriptionConstructor)
            and not refresh
            and expires_at == 0
        ):
            expected_expiry = -1
        assert isinstance(result, OAuthCredentials)
        assert result.model_dump(mode="json") == {
            "credentials": credentials,
            "metadata": metadata,
            "expires_at": expected_expiry,
        }

    assert calls == [
        (
            redirect_uri,
            system_credentials,
            previous_credentials if refresh else callback_request,
        )
    ]
    assert callback_request.args["code"] == "authorization-code"
    assert callback_request.get_data() == b"body"
    assert previous_credentials == previous_payload
    assert source.model_dump() == source_payload


@pytest.mark.parametrize(
    "method",
    [
        "get_authorization_url",
        "get_credentials",
        "refresh_credentials",
        "revoke_credentials",
    ],
)
def test_oauth_provider_errors_reach_the_caller(
    oauth_provider: ToolProvider | DatasourceProvider | TriggerSubscriptionConstructor,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    error = ToolProviderOAuthError("authorization expired")

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    monkeypatch.setattr(oauth_provider, f"_oauth_{method}", fail)
    args = ["https://example.test/callback", {}]
    if method == "get_credentials":
        args.append(Request.from_values())
    elif method == "refresh_credentials":
        args.append({"refresh_token": "expired"})
    elif method == "revoke_credentials":
        args = [{}, {"access_token": "token"}]

    with pytest.raises(ToolProviderOAuthError) as caught:
        getattr(oauth_provider, f"oauth_{method}")(*args)
    assert caught.value is error


def test_oauth_revocation_requires_implementation(
    oauth_provider: ToolProvider | DatasourceProvider | TriggerSubscriptionConstructor,
) -> None:
    with pytest.raises(NotImplementedError, match="_oauth_revoke_credentials"):
        oauth_provider.oauth_revoke_credentials({}, {"access_token": "token"})
