from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.datasource import DatasourceOAuthCredentials
from dify_plugin.protocol.oauth import OAuthCredentials


class DatasourceProvider:
    """
    A provider for a datasource
    """

    def validate_credentials(self, credentials: Mapping[str, Any]):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: Mapping[str, Any]):
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(redirect_uri, system_credentials)

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> OAuthCredentials:
        datasource_credentials = self._oauth_get_credentials(redirect_uri, system_credentials, request)
        return OAuthCredentials(
            metadata={
                "avatar_url": datasource_credentials.avatar_url,
                "name": datasource_credentials.name,
            },
            credentials=datasource_credentials.credentials,
            expires_at=datasource_credentials.expires_at,
        )

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> DatasourceOAuthCredentials:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        """
        Refresh the credentials

        :param redirect_uri: redirect uri
        :param system_credentials: system credentials
        :param credentials: credentials
        :return: refreshed credentials
        """
        datasource_credentials = self._oauth_refresh_credentials(redirect_uri, system_credentials, credentials)
        return OAuthCredentials(
            metadata={
                "avatar_url": datasource_credentials.avatar_url,
                "name": datasource_credentials.name,
            },
            credentials=datasource_credentials.credentials,
            expires_at=datasource_credentials.expires_at,
        )

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> DatasourceOAuthCredentials:
        raise NotImplementedError(
            "The tool you are using does not support OAuth, please implement `_oauth_refresh_credentials` method"
        )
