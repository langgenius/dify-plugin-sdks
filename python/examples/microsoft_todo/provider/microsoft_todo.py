import json
from collections.abc import Mapping
from pprint import pprint as debug_print
from typing import Any

from pymstodo import ToDoConnection
from pymstodo.client import Token
from requests_oauthlib import OAuth2Session
from werkzeug import Request

from dify_plugin import ToolProvider
from dify_plugin.entities.oauth import ToolOAuthCredentials
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class MicrosoftTodoProvider(ToolProvider):
    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        debug_print(f"Redirect URI: {redirect_uri}")
        debug_print(f"System Credentials: {system_credentials}")

        client_id = system_credentials.get("client_id")
        if not client_id:
            raise ToolProviderCredentialValidationError("Client ID is required for OAuth.")

        ToDoConnection._redirect = redirect_uri

        return ToDoConnection.get_auth_url(client_id)

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> ToolOAuthCredentials:
        debug_print(f"Redirect URI: {redirect_uri}")
        debug_print(f"System Credentials: {system_credentials}")

        code = request.args.get("code")
        if not code:
            raise ToolProviderCredentialValidationError("Authorization code is missing in the request.")

        ToDoConnection._redirect = redirect_uri
        token_url = f"{ToDoConnection._authority}{ToDoConnection._token_endpoint}"

        oa_sess = OAuth2Session(
            system_credentials["client_id"],
            scope=ToDoConnection._scope,
            redirect_uri=ToDoConnection._redirect,
        )
        token = oa_sess.fetch_token(token_url, client_secret=system_credentials["client_secret"], code=code)
        expires_at = token["expires_at"]
        return ToolOAuthCredentials(credentials={"token": json.dumps(token)}, expires_at=expires_at)

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> ToolOAuthCredentials:
        debug_print(f"Redirect URI: {redirect_uri}")
        debug_print(f"System Credentials: {system_credentials}")
        debug_print(f"Credentials: {credentials}")

        ToDoConnection._redirect = redirect_uri
        token_url = f"{ToDoConnection._authority}{ToDoConnection._token_endpoint}"
        token = json.loads(credentials["token"])
        refresh_token = token["refresh_token"]
        oa_sess = OAuth2Session(
            system_credentials["client_id"],
            scope=ToDoConnection._scope,
            redirect_uri=ToDoConnection._redirect,
        )
        new_token = oa_sess.refresh_token(
            token_url,
            refresh_token=refresh_token,
            client_id=system_credentials["client_id"],
            client_secret=system_credentials["client_secret"],
        )
        expires_at = new_token["expires_at"]
        return ToolOAuthCredentials(credentials={"token": json.dumps(new_token)}, expires_at=expires_at)

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        debug_print(f"Validating credentials: {credentials}")

        try:
            token: Token = Token(**json.loads(credentials["token"]))
            if not token.access_token:
                raise ToolProviderCredentialValidationError("Access token is missing.")

            todo_client = ToDoConnection(
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"],
                token=token,
            )

            lists = todo_client.get_lists()
            debug_print(f"Retrieved lists: {lists}")
            raise Exception(f"token: {token}\nlists: {lists}\ncredentials: {credentials}")

        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
