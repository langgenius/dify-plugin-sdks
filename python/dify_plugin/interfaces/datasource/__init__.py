from collections.abc import Mapping
from typing import Any

from werkzeug import Request


class DatasourceProvider:
    """
    A provider for a datasource
    """

    def validate_credentials(self, credentials: Mapping[str, Any]):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: Mapping[str, Any]):
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(system_credentials)

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return self._oauth_get_credentials(system_credentials, request)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        raise NotImplementedError("This method should be implemented by a subclass")
