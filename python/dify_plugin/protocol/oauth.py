from collections.abc import Mapping
from typing import Any, Protocol

from werkzeug import Request


class OAuthProviderProtocol(Protocol):
    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        """
        Get the authorization url
        :param system_credentials: system credentials
        :return: authorization url
        """
        ...

    def oauth_get_credentials(
        self,
        system_credentials: Mapping[str, Any],
        request: Request,
    ) -> Mapping[str, Any]:
        """
        Get the credentials
        :param request: request
        :param system_credentials: system credentials
        :return: credentials
        """
        ...
