from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

from werkzeug import Request

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import (
    OAuthCredentials,
    OAuthRevokeResult,
    TriggerOAuthCredentials,
)
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import Subscription, UnsubscribeResult
from dify_plugin.interfaces.trigger import TriggerSubscriptionConstructor


class ContractConstructor(TriggerSubscriptionConstructor):
    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        if credentials.get("api_key") != "valid":
            msg = "invalid credentials"
            raise ValueError(msg)

    def _oauth_get_authorization_url(
        self, redirect_uri: str, system_credentials: Mapping[str, Any]
    ) -> str:
        return "https://provider.invalid/authorize?" + urlencode({
            "redirect_uri": redirect_uri,
            "client_id": system_credentials["client_id"],
        })

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        del redirect_uri, system_credentials
        return TriggerOAuthCredentials(
            credentials={
                "access_token": "token-" + request.args["code"],
                "refresh_token": "refresh",
            }
        )

    def _oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> OAuthCredentials:
        del redirect_uri, system_credentials
        return OAuthCredentials(
            credentials={**credentials, "access_token": "refreshed"}
        )

    def _oauth_revoke_credentials(
        self,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> OAuthRevokeResult:
        del system_credentials, credentials
        return OAuthRevokeResult(status="revoked", reason_code=None, retryable=False)

    def _create_subscription(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        self.last_credentials = credentials
        return Subscription(
            endpoint=endpoint,
            parameters=parameters,
            expires_at=100,
            properties={
                "external_id": "subscription",
                "credential_type": credential_type.value,
            },
        )

    def _refresh_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> Subscription:
        self.last_credentials = credentials
        self.last_credential_type = credential_type
        return subscription.model_copy(update={"expires_at": 200})

    def _delete_subscription(
        self,
        subscription: Subscription,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> UnsubscribeResult:
        self.last_credentials = credentials
        self.last_credential_type = credential_type
        return UnsubscribeResult(
            success=credentials.get("api_key") != "invalid",
            message=subscription.properties["external_id"],
        )

    def _fetch_parameter_options(
        self,
        parameter: str,
        credentials: Mapping[str, Any],
        credential_type: CredentialType,
    ) -> list[ParameterOption]:
        self.last_credentials = credentials
        self.last_credential_type = credential_type
        return [ParameterOption(value="echo", label=I18nObject(en_us=parameter))]
