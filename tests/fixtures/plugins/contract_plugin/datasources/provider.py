from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

from werkzeug import Request

from dify_plugin.entities.datasource import DatasourceOAuthCredentials
from dify_plugin.interfaces.datasource import DatasourceProvider


class ContractDatasourceProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
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
    ) -> DatasourceOAuthCredentials:
        del redirect_uri, system_credentials
        return DatasourceOAuthCredentials(
            credentials={
                "access_token": "token-" + request.args["code"],
                "refresh_token": "refresh",
            },
            name="Contract account",
            avatar_url="https://provider.invalid/avatar.png",
        )

    def _oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> DatasourceOAuthCredentials:
        del redirect_uri, system_credentials
        return DatasourceOAuthCredentials(
            credentials={**credentials, "access_token": "refreshed"},
            name="Contract account",
            avatar_url="https://provider.invalid/avatar.png",
        )
