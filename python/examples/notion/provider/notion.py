import urllib.parse
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.interfaces.datasource import DatasourceProvider


class NotionDatasourceProvider(DatasourceProvider):
    _AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
    _TOKEN_URL = "https://api.notion.com/v1/oauth/token"

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Generate the authorization URL for the Notion OAuth.
        """
        params = {
            "client_id": system_credentials["client_id"],
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "owner": "user",
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> Mapping[str, Any]:
        """
        Get the credentials for the Notion OAuth.
        """
        code = request.args.get("code")
        if not code:
            raise ValueError("No code provided")

        data = {"code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri}
        headers = {"Accept": "application/json"}
        auth = (system_credentials["client_id"], system_credentials["client_secret"])
        response = requests.post(self._TOKEN_URL, data=data, auth=auth, headers=headers, timeout=10)
        response_json = response.json()
        access_token = response_json.get("access_token")
        if not access_token:
            raise ValueError(f"Error in Notion OAuth: {response_json}")

        workspace_name = response_json.get("workspace_name")
        workspace_icon = response_json.get("workspace_icon")
        workspace_id = response_json.get("workspace_id")
        # get all authorized pages

        return {
            "access_token": access_token,
            "workspace_name": workspace_name,
            "workspace_icon": workspace_icon,
            "workspace_id": workspace_id,
        }

    def _validate_credentials(self, credentials: Mapping[str, Any]):
        """
        Validate the credentials for the Notion datasource provider.
        """
        pass
