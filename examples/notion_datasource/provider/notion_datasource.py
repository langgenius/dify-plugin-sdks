from collections.abc import Mapping
from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode

import urllib3_future
from werkzeug import Request

from dify_plugin.entities.datasource import DatasourceOAuthCredentials
from dify_plugin.errors.tool import (
    DatasourceOAuthError,
    ToolProviderCredentialValidationError,
)
from dify_plugin.interfaces.datasource import DatasourceProvider

__TIMEOUT_SECONDS__ = 60 * 10


class NotionDatasourceProvider(DatasourceProvider):
    API_VERSION = "2022-06-28"  # Using a stable API version
    _AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
    _OAUTH_ENDPOINT = "https://api.notion.com/v1/oauth/token"

    def _oauth_get_authorization_url(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
    ) -> str:
        """Generate the authorization URL for the Notion OAuth."""
        params = {
            "client_id": system_credentials["client_id"],
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "owner": "user",
        }
        return f"{self._AUTH_URL}?{urlencode(params)}"

    def _oauth_get_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        request: Request,
    ) -> DatasourceOAuthCredentials:
        """Get the credentials for the Notion OAuth."""
        code = request.args.get("code")
        if not code:
            msg = "No code provided"
            raise DatasourceOAuthError(msg)

        data = {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        headers = urllib3_future.make_headers(
            basic_auth=(
                f"{system_credentials['client_id']}:"
                f"{system_credentials['client_secret']}"
            )
        )
        headers.update({
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        response = urllib3_future.request(
            "POST",
            self._OAUTH_ENDPOINT,
            body=urlencode(data),
            headers=headers,
            timeout=__TIMEOUT_SECONDS__,
        )
        response_json = response.json()
        access_token = response_json.get("access_token")
        if not access_token:
            msg = f"Error in Notion OAuth: {response_json}"
            raise DatasourceOAuthError(msg)

        workspace_name = response_json.get("workspace_name")
        workspace_icon = response_json.get("workspace_icon")
        workspace_id = response_json.get("workspace_id")

        return DatasourceOAuthCredentials(
            name=workspace_name,
            avatar_url=workspace_icon,
            credentials={
                "integration_secret": access_token,
                "workspace_name": workspace_name,
                "workspace_icon": workspace_icon,
                "workspace_id": workspace_id,
            },
        )

    def _oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> DatasourceOAuthCredentials:
        """Refresh the credentials for the Notion OAuth.

        Note: Notion OAuth API does not support refresh tokens.
        When the access token expires, users need to re-authorize through the
        OAuth flow.
        """

    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        integration_secret = credentials.get("integration_secret")
        if not integration_secret:
            msg = "Notion Integration Token is required."
            raise ToolProviderCredentialValidationError(msg)

        try:
            response = urllib3_future.request(
                "GET",
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {integration_secret}",
                    "Notion-Version": self.API_VERSION,
                },
                timeout=__TIMEOUT_SECONDS__,
            )
        except urllib3_future.exceptions.HTTPError as e:
            msg = f"Network error when connecting to Notion API: {e!s}"
            raise ToolProviderCredentialValidationError(msg) from e

        if response.status == HTTPStatus.UNAUTHORIZED:
            msg = "Invalid Notion Integration Token."
            raise ToolProviderCredentialValidationError(msg)
        if response.status != HTTPStatus.OK:
            msg = (
                f"Failed to connect to Notion API: "
                f"{response.status} {response.data.decode(errors='replace')}"
            )
            raise ToolProviderCredentialValidationError(msg)
