import hashlib
import hmac
import secrets
import time
import urllib.parse
import uuid
from collections.abc import Mapping
from typing import Any

import requests
from werkzeug import Request, Response

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import TriggerOAuthCredentials
from dify_plugin.entities.trigger import Subscription, TriggerDispatch, Unsubscription
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerDispatchError,
    TriggerProviderCredentialValidationError,
    TriggerProviderOAuthError,
    TriggerValidationError,
)
from dify_plugin.interfaces.trigger import TriggerProvider
from examples.github_trigger.utils.dynamic_options import fetch_repositories


class GithubProvider(TriggerProvider):
    _AUTH_URL = "https://github.com/login/oauth/authorize"
    _TOKEN_URL = "https://github.com/login/oauth/access_token"
    _API_USER_URL = "https://api.github.com/user"

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Generate the authorization URL for the Github OAuth.
        """
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "redirect_uri": redirect_uri,
            # must contain webhook scope
            "scope": system_credentials.get("scope", "read:user admin:repo_hook"),
            "state": state,
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        """
        Exchange code for access_token.
        """
        code = request.args.get("code")
        if not code:
            raise TriggerProviderOAuthError("No code provided")
        # Optionally: validate state here

        data = {
            "client_id": system_credentials["client_id"],
            "client_secret": system_credentials["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
        }
        headers = {"Accept": "application/json"}
        response = requests.post(self._TOKEN_URL, data=data, headers=headers, timeout=10)
        response_json = response.json()
        access_tokens = response_json.get("access_token")
        if not access_tokens:
            raise TriggerProviderOAuthError(f"Error in GitHub OAuth: {response_json}")

        return TriggerOAuthCredentials(credentials={"access_tokens": access_tokens}, expires_at=-1)

    def _validate_credentials(self, credentials: dict) -> None:
        try:
            if "access_tokens" not in credentials or not credentials.get("access_tokens"):
                raise TriggerProviderCredentialValidationError("GitHub API Access Token is required.")
            headers = {
                "Authorization": f"Bearer {credentials['access_tokens']}",
                "Accept": "application/vnd.github+json",
            }
            response = requests.get(self._API_USER_URL, headers=headers, timeout=10)
            if response.status_code != 200:
                raise TriggerProviderCredentialValidationError(response.json().get("message"))
        except Exception as e:
            raise TriggerProviderCredentialValidationError(str(e)) from e

    def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Dispatch GitHub webhook events - focusing on issue comment events
        """
        # Verify webhook signature if secret is provided
        webhook_secret = subscription.properties.get("webhook_secret")
        if webhook_secret:
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                raise TriggerValidationError("Missing webhook signature")

            # Verify the signature
            expected_signature = (
                "sha256=" + hmac.new(webhook_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
            )

            if not hmac.compare_digest(signature, expected_signature):
                raise TriggerValidationError("Invalid webhook signature")

        event_type = request.headers.get("X-GitHub-Event")
        if not event_type:
            raise TriggerDispatchError("Missing GitHub event type header")

        try:
            # GitHub webhooks can send data as form-encoded or JSON
            content_type = request.headers.get("Content-Type", "")

            if "application/x-www-form-urlencoded" in content_type:
                # For form-encoded data, the payload is in the 'payload' field
                import json

                form_data = request.form.get("payload")
                if not form_data:
                    raise TriggerDispatchError("Missing payload in form data")
                payload = json.loads(form_data)
            else:
                # For JSON content type or when Content-Type is missing/other
                payload = request.get_json(force=True)

            if not payload:
                raise TriggerDispatchError("Empty request body")
        except Exception as e:
            raise TriggerDispatchError(f"Failed to parse payload: {e}") from e

        response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")

        # Create trigger event dispatch with GitHub event type
        # Map GitHub events to our trigger events
        if event_type == "issue_comment":
            return TriggerDispatch(triggers=["issue_comment"], response=response)
        elif event_type == "issues":
            # Issues event can trigger multiple workflows based on action
            action = payload.get("action")
            if action == "opened":
                # Dispatch both generic issues event and specific opened event
                return TriggerDispatch(triggers=["issues", "issues.opened"], response=response)
            elif action == "closed":
                return TriggerDispatch(triggers=["issues", "issues.closed"], response=response)
            else:
                return TriggerDispatch(triggers=["issues"], response=response)
        else:
            # For other events, pass them through with prefix
            return TriggerDispatch(triggers=[f"github.{event_type}"], response=response)

    def _subscribe(self, endpoint: str, credentials: Mapping[str, Any], parameters: Mapping[str, Any]) -> Subscription:
        """
        Create a GitHub webhook subscription for issue comment events
        """
        # Extract parameters
        webhook_id = uuid.uuid4().hex
        webhook_secret = webhook_id
        repository = parameters.get("repository")  # format: "owner/repo"
        events = parameters.get("events", ["issue_comment", "issues"])

        if not repository:
            raise ValueError("repository is required (format: owner/repo)")

        # Parse repository owner and name
        try:
            owner, repo = repository.split("/")
        except ValueError:
            raise ValueError("repository must be in format 'owner/repo'") from None

        # Create webhook using GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/hooks"
        headers = {
            "Authorization": f"Bearer {credentials.get('access_tokens')}",
            "Accept": "application/vnd.github+json",
        }

        webhook_data = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {"url": endpoint, "content_type": "json", "insecure_ssl": "0"},
        }

        # Add secret if provided
        if webhook_secret:
            webhook_data["config"]["secret"] = webhook_secret

        try:
            response = requests.post(url, json=webhook_data, headers=headers, timeout=10)
            if response.status_code == 201:
                webhook = response.json()
                # Return subscription with webhook details
                return Subscription(
                    expires_at=int(time.time()) + 30 * 24 * 60 * 60,  # 30 days expiration
                    endpoint=endpoint,
                    properties={
                        "external_id": str(webhook["id"]),
                        "repository": repository,
                        "events": events,
                        "webhook_secret": webhook_secret,
                        "active": webhook["active"],
                    },
                )
            else:
                response_data = response.json() if response.content else {}
                error_msg = response_data.get("message", "Unknown error")
                error_details = response_data.get("errors", [])

                # Log detailed error information for debugging
                print(f"GitHub webhook creation failed with status {response.status_code}")
                print(f"Request URL: {url}")
                print(f"Request data: {webhook_data}")
                print(f"Response: {response_data}")

                detailed_error = f"Failed to create GitHub webhook: {error_msg}"
                if error_details:
                    detailed_error += f" Details: {error_details}"

                raise SubscriptionError(
                    detailed_error,
                    error_code="WEBHOOK_CREATION_FAILED",
                    external_response=response_data,
                )
        except requests.RequestException as e:
            raise SubscriptionError(f"Network error while creating webhook: {e}", error_code="NETWORK_ERROR") from e

    def _unsubscribe(self, endpoint: str, subscription: Subscription, credentials: Mapping[str, Any]) -> Unsubscription:
        """
        Remove a GitHub webhook subscription
        """
        # Extract webhook details from properties
        external_id = subscription.properties.get("external_id")
        repository = subscription.properties.get("repository")

        if not external_id or not repository:
            return Unsubscription(
                success=False, message="Missing webhook ID or repository information", error_code="MISSING_PROPERTIES"
            )

        # Parse repository
        try:
            owner, repo = repository.split("/")
        except ValueError:
            return Unsubscription(
                success=False, message="Invalid repository format in properties", error_code="INVALID_REPOSITORY"
            )

        # Delete webhook using GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/hooks/{external_id}"
        headers = {
            "Authorization": f"Bearer {credentials.get('access_tokens')}",
            "Accept": "application/vnd.github+json",
        }

        try:
            response = requests.delete(url, headers=headers, timeout=10)
            if response.status_code == 204:
                return Unsubscription(
                    success=True, message=f"Successfully removed webhook {external_id} from {repository}"
                )
            elif response.status_code == 404:
                return Unsubscription(
                    success=False,
                    message=f"Webhook {external_id} not found in repository {repository}",
                    error_code="WEBHOOK_NOT_FOUND",
                )
            else:
                return Unsubscription(
                    success=False,
                    message=f"Failed to delete webhook: {response.json().get('message', 'Unknown error')}",
                    error_code="API_ERROR",
                    external_response=response.json(),
                )
        except requests.RequestException as e:
            return Unsubscription(
                success=False, message=f"Network error while deleting webhook: {e}", error_code="NETWORK_ERROR"
            )

    def _refresh(self, endpoint: str, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        """
        Refresh a GitHub webhook subscription (extend expiration)
        GitHub webhooks don't expire, so we just extend our internal expiration
        """
        # Simply return the subscription with extended expiration
        # GitHub webhooks don't have built-in expiration
        return Subscription(
            expires_at=int(time.time()) + 30 * 24 * 60 * 60,  # Extend by 30 days
            endpoint=endpoint,  # Keep the same endpoint
            properties=subscription.properties,  # Keep the same properties
        )

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter == "repository":
            return fetch_repositories(self.runtime.credentials.get("access_tokens"))

        return [
            ParameterOption(
                value="iamjoel",
                label=I18nObject(en_US="Joel"),
                icon="https://avatars.githubusercontent.com/u/2120155?s=40&v=4",
            ),
            ParameterOption(
                value="yeuoly",
                label=I18nObject(en_US="Yeuoly"),
                icon="https://avatars.githubusercontent.com/u/45712896?s=60&v=4",
            ),
        ]
