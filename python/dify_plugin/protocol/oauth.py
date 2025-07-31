from collections.abc import Mapping
from typing import Any, Protocol

from werkzeug import Request

from dify_plugin.entities.oauth import OAuthCredentials


class OAuthProviderProtocol(Protocol):
    def oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Get the authorization url
        :param redirect_uri: redirect uri for the callback
        :param system_credentials: system credentials
        :return: authorization url
        """
        ...

    def oauth_get_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        request: Request,
    ) -> OAuthCredentials:
        """
        Get the credentials
        :param redirect_uri: redirect uri
        :param request: request
        :param system_credentials: system credentials
        :return: { "metadata": { "avatar_url": str, "name": str }, "credentials": credentials }
        """
        ...

    def oauth_refresh_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        credentials: Mapping[str, Any],
    ) -> OAuthCredentials:
        """
        Refresh the credentials
        :param redirect_uri: redirect uri
        :param system_credentials: system credentials
        :param credentials: credentials
        :return: credentials
        """
        ...
