import hashlib
import hmac
import secrets
import time
import urllib.parse
import uuid
from collections.abc import Mapping
from typing import Any, ClassVar

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


class GithubProvider(TriggerProvider):
    _AUTH_URL = "https://github.com/login/oauth/authorize"
    _TOKEN_URL = "https://github.com/login/oauth/access_token"
    _API_USER_URL = "https://api.github.com/user"

    _TRIGGER_EVENTS: ClassVar[dict[str, list[str]]] = {
        "issues": ["issues"],
        "issues_comment": ["issues_comment"],
    }

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": system_credentials["client_id"],
            "redirect_uri": redirect_uri,
            "scope": system_credentials.get("scope", "read:user admin:repo_hook"),
            "state": state,
        }
        return f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        code = request.args.get("code")
        if not code:
            raise TriggerProviderOAuthError("No code provided")
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
        if False:
            webhook_secret = subscription.properties.get("webhook_secret")
            if webhook_secret:
                signature = request.headers.get("X-Hub-Signature-256")
                if not signature:
                    raise TriggerValidationError("Missing webhook signature")
                expected_signature = (
                    "sha256=" + hmac.new(webhook_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
                )
                if not hmac.compare_digest(signature, expected_signature):
                    raise TriggerValidationError("Invalid webhook signature")

        event_type = request.headers.get("X-GitHub-Event")
        if not event_type:
            raise TriggerDispatchError("Missing GitHub event type header")

        try:
            content_type = request.headers.get("Content-Type", "")
            if "application/x-www-form-urlencoded" in content_type:
                import json

                form_data = request.form.get("payload")
                if not form_data:
                    raise TriggerDispatchError("Missing payload in form data")
                payload = json.loads(form_data)
            else:
                payload = request.get_json(force=True)
            if not payload:
                raise TriggerDispatchError("Empty request body")
        except Exception as e:
            raise TriggerDispatchError(f"Failed to parse payload: {e}") from e

        triggers = self._TRIGGER_EVENTS.get(event_type, [])
        return TriggerDispatch(
            triggers=triggers, response=Response(response='{"status": "ok"}', status=200, mimetype="application/json")
        )

    def _subscribe(self, endpoint: str, credentials: Mapping[str, Any], parameters: Mapping[str, Any]) -> Subscription:
        webhook_id = uuid.uuid4().hex
        webhook_secret = webhook_id
        repository = parameters.get("repository")
        events = parameters.get("events", ["issue_comment", "issues"])

        if not repository:
            raise ValueError("repository is required (format: owner/repo)")

        try:
            owner, repo = repository.split("/")
        except ValueError:
            raise ValueError("repository must be in format 'owner/repo'") from None

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

        if webhook_secret:
            webhook_data["config"]["secret"] = webhook_secret

        try:
            response = requests.post(url, json=webhook_data, headers=headers, timeout=10)
            if response.status_code == 201:
                webhook = response.json()
                return Subscription(
                    expires_at=int(time.time()) + 30 * 24 * 60 * 60,
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
        external_id = subscription.properties.get("external_id")
        repository = subscription.properties.get("repository")

        if not external_id or not repository:
            return Unsubscription(
                success=False, message="Missing webhook ID or repository information", error_code="MISSING_PROPERTIES"
            )

        try:
            owner, repo = repository.split("/")
        except ValueError:
            return Unsubscription(
                success=False, message="Invalid repository format in properties", error_code="INVALID_REPOSITORY"
            )

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
        return Subscription(
            expires_at=int(time.time()) + 30 * 24 * 60 * 60,
            endpoint=endpoint,
            properties=subscription.properties,
        )

    def _fetch_repositories(self, access_token: str) -> list[ParameterOption]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        options: list[ParameterOption] = []
        per_page = 100
        page = 1

        while True:
            params = {
                "per_page": per_page,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
                "sort": "full_name",
                "direction": "asc",
            }

            response = requests.get("https://api.github.com/user/repos", headers=headers, params=params, timeout=10)

            if response.status_code != 200:
                try:
                    err = response.json()
                    message = err.get("message", str(err))
                except Exception:
                    message = response.text
                raise ValueError(f"Failed to fetch repositories from GitHub: {message}")

            repos = response.json() or []
            if not isinstance(repos, list):
                raise ValueError("Unexpected response format from GitHub API when fetching repositories")

            for repo in repos:
                full_name = repo.get("full_name")
                owner = repo.get("owner") or {}
                avatar_url = owner.get("avatar_url")
                if full_name:
                    options.append(
                        ParameterOption(
                            value=full_name,
                            label=I18nObject(en_US=full_name),
                            icon=avatar_url,
                        )
                    )

            if len(repos) < per_page:
                break

            page += 1

        return options

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter == "repository":
            token = self.runtime.credentials.get("access_tokens")
            if not token:
                raise ValueError("access_tokens is required")
            return self._fetch_repositories(token)

        return []
