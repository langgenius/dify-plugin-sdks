import hashlib
import hmac
import json
import secrets
import urllib.parse
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.interfaces.trigger import TriggerProvider
from dify_plugin.entities.trigger import TriggerEventDispatch
from dify_plugin.entities.oauth import ToolOAuthCredentials
from dify_plugin.errors.tool import ToolProviderCredentialValidationError, ToolProviderOAuthError


class GithubProvider(TriggerProvider):
    _AUTH_URL = "https://github.com/login/oauth/authorize"
    _TOKEN_URL = "https://github.com/login/oauth/access_token"
    _API_USER_URL = "https://api.github.com/user"

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        """
        Generate the authorization URL for the Github OAuth.
        """
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "scope": system_credentials.get("scope", "repo"),
            "state": state,
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        """
        Exchange code for access_token.
        """
        code = request.args.get("code")
        if not code:
            raise ToolProviderOAuthError("No code provided")

        data = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "code": code,
        }
        headers = {"Accept": "application/json"}
        response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        response_json = response.json()
        access_token = response_json.get("access_token")
        if not access_token:
            raise ToolProviderOAuthError(f"Error in GitHub OAuth: {response_json}")

        return {"access_tokens": access_token}

    def _validate_credentials(self, credentials: dict) -> None:
        try:
            if "access_tokens" not in credentials or not credentials.get("access_tokens"):
                raise ToolProviderCredentialValidationError("GitHub API Access Token is required.")
            headers = {
                "Authorization": f"Bearer {credentials['access_tokens']}",
                "Accept": "application/vnd.github+json",
            }
            response = requests.get(self._API_USER_URL, headers=headers, timeout=10)
            if response.status_code != 200:
                raise ToolProviderCredentialValidationError(response.json().get("message"))
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e

    def _dispatch_event(self, settings: Mapping[str, Any], request: Request) -> TriggerEventDispatch:
        """
        Dispatch GitHub webhook events
        """
        # Verify webhook signature if secret is provided
        webhook_secret = settings.get("webhook_secret")
        if webhook_secret:
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                raise ValueError("Missing webhook signature")

            # Verify the signature
            expected_signature = (
                "sha256=" + hmac.new(webhook_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
            )

            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("Invalid webhook signature")

        event_type = request.headers.get("X-GitHub-Event")
        if not event_type:
            raise ValueError("Missing GitHub event type header")

        try:
            payload = request.get_json()
            if not payload:
                raise ValueError("Empty request body")
        except Exception as e:
            raise ValueError(f"Failed to parse JSON payload: {e}")

        from werkzeug import Response

        response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")

        # Create trigger event dispatch with GitHub event type
        return TriggerEventDispatch(event=f"github.{event_type}", response=response)
