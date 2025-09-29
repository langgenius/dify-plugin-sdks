from __future__ import annotations

import hashlib
import hmac
import json
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
from dify_plugin.entities.trigger import Subscription, TriggerDispatch, UnsubscribeResult
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerDispatchError,
    TriggerProviderCredentialValidationError,
    TriggerProviderOAuthError,
    TriggerValidationError,
    UnsubscribeError,
)
from dify_plugin.interfaces.trigger import TriggerProvider, TriggerSubscriptionConstructor


class GithubProvider(TriggerProvider):
    """Handle GitHub webhook event dispatch."""

    __TRIGGER_EVENTS_MAPPING: ClassVar[Mapping[str, Mapping[str, list[str]]]] = {
        "issues": {
            "opened": ["issue_opened"],
        }
    }

    def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        webhook_secret = subscription.properties.get("webhook_secret")
        if webhook_secret:
            self._validate_signature(request, webhook_secret)

        event_type = request.headers.get("X-GitHub-Event")
        if not event_type:
            raise TriggerDispatchError("Missing GitHub event type header")

        payload = self._validate_payload(request)
        triggers = self._dispatch_event_triggers(event_type, payload)
        response = Response(response='{"status": "ok"}', status=200, mimetype="application/json")
        return TriggerDispatch(triggers=triggers, response=response)

    def _dispatch_event_triggers(self, event_type: str, payload: Mapping[str, Any]) -> list[str]:
        event_type = event_type.lower()
        if event_type == "issues":
            action = payload.get("action")
            return self.__TRIGGER_EVENTS_MAPPING["issues"].get(action, [])
        return []

    def _validate_payload(self, request: Request) -> Mapping[str, Any]:
        try:
            content_type = request.headers.get("Content-Type", "")
            if "application/x-www-form-urlencoded" in content_type:
                form_data = request.form.get("payload")
                if not form_data:
                    raise TriggerDispatchError("Missing payload in form data")
                payload = json.loads(form_data)
            else:
                payload = request.get_json(force=True)
            if not payload:
                raise TriggerDispatchError("Empty request body")
            return payload
        except TriggerDispatchError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging path
            raise TriggerDispatchError(f"Failed to parse payload: {exc}") from exc

    def _validate_signature(self, request: Request, webhook_secret: str) -> None:
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise TriggerValidationError("Missing webhook signature")

        expected_signature = (
            "sha256=" + hmac.new(webhook_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(signature, expected_signature):
            raise TriggerValidationError("Invalid webhook signature")


class GithubSubscriptionConstructor(TriggerSubscriptionConstructor):
    """Manage GitHub trigger subscriptions."""

    _AUTH_URL = "https://github.com/login/oauth/authorize"
    _TOKEN_URL = "https://github.com/login/oauth/access_token"
    _API_USER_URL = "https://api.github.com/user"
    _WEBHOOK_TTL = 30 * 24 * 60 * 60

    def _validate_api_key(self, credentials: dict) -> None:
        access_token = credentials.get("access_tokens")
        if not access_token:
            raise TriggerProviderCredentialValidationError("GitHub API Access Token is required.")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        try:
            response = requests.get(self._API_USER_URL, headers=headers, timeout=10)
            if response.status_code != 200:
                raise TriggerProviderCredentialValidationError(response.json().get("message"))
        except TriggerProviderCredentialValidationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging path
            raise TriggerProviderCredentialValidationError(str(exc)) from exc

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

        if not system_credentials.get("client_id") or not system_credentials.get("client_secret"):
            raise TriggerProviderOAuthError("Client ID or Client Secret is required")

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

    def _create_subscription(
        self,
        endpoint: str,
        credentials: Mapping[str, Any],
        selected_events: list[str],
        parameters: Mapping[str, Any],
    ) -> Subscription:
        repository = parameters.get("repository")
        if not repository:
            raise ValueError("repository is required (format: owner/repo)")

        try:
            owner, repo = repository.split("/")
        except ValueError:
            raise ValueError("repository must be in format 'owner/repo'") from None

        events = self._resolve_webhook_events(selected_events)
        webhook_secret = uuid.uuid4().hex

        url = f"https://api.github.com/repos/{owner}/{repo}/hooks"
        headers = {
            "Authorization": f"Bearer {credentials.get('access_tokens')}",
            "Accept": "application/vnd.github+json",
        }

        webhook_data = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {"url": endpoint, "content_type": "json", "insecure_ssl": "0", "secret": webhook_secret},
        }

        try:
            response = requests.post(url, json=webhook_data, headers=headers, timeout=10)
        except requests.RequestException as exc:
            raise SubscriptionError(f"Network error while creating webhook: {exc}", error_code="NETWORK_ERROR") from exc

        if response.status_code == 201:
            webhook = response.json()
            return Subscription(
                expires_at=int(time.time()) + self._WEBHOOK_TTL,
                endpoint=endpoint,
                properties={
                    "external_id": str(webhook["id"]),
                    "repository": repository,
                    "events": events,
                    "webhook_secret": webhook_secret,
                    "active": webhook.get("active", True),
                },
            )

        response_data = response.json() if response.content else {}
        error_msg = response_data.get("message", "Unknown error")
        error_details = response_data.get("errors", [])
        detailed_error = f"Failed to create GitHub webhook: {error_msg}"
        if error_details:
            detailed_error += f" Details: {error_details}"

        raise SubscriptionError(
            detailed_error,
            error_code="WEBHOOK_CREATION_FAILED",
            external_response=response_data,
        )

    def _delete_subscription(self, subscription: Subscription, credentials: Mapping[str, Any]) -> UnsubscribeResult:
        external_id = subscription.properties.get("external_id")
        repository = subscription.properties.get("repository")

        if not external_id or not repository:
            raise UnsubscribeError(
                message="Missing webhook ID or repository information",
                error_code="MISSING_PROPERTIES",
                external_response=None,
            )

        try:
            owner, repo = repository.split("/")
        except ValueError:
            raise UnsubscribeError(
                message="Invalid repository format in properties",
                error_code="INVALID_REPOSITORY",
                external_response=None,
            ) from None

        url = f"https://api.github.com/repos/{owner}/{repo}/hooks/{external_id}"
        headers = {
            "Authorization": f"Bearer {credentials.get('access_tokens')}",
            "Accept": "application/vnd.github+json",
        }

        try:
            response = requests.delete(url, headers=headers, timeout=10)
        except requests.RequestException as exc:
            raise UnsubscribeError(
                message=f"Network error while deleting webhook: {exc}",
                error_code="NETWORK_ERROR",
                external_response=None,
            ) from exc

        if response.status_code == 204:
            return UnsubscribeResult(
                success=True, message=f"Successfully removed webhook {external_id} from {repository}"
            )

        if response.status_code == 404:
            raise UnsubscribeError(
                message=f"Webhook {external_id} not found in repository {repository}",
                error_code="WEBHOOK_NOT_FOUND",
                external_response=response.json(),
            )

        raise UnsubscribeError(
            message=f"Failed to delete webhook: {response.json().get('message', 'Unknown error')}",
            error_code="WEBHOOK_DELETION_FAILED",
            external_response=response.json(),
        )

    def _refresh(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        return Subscription(
            expires_at=int(time.time()) + self._WEBHOOK_TTL,
            endpoint=subscription.endpoint,
            properties=subscription.properties,
        )

    def _fetch_parameter_options(self, credentials: Mapping[str, Any], parameter: str) -> list[ParameterOption]:
        if parameter != "repository":
            return []

        token = credentials.get("access_tokens")
        if not token:
            raise ValueError("access_tokens is required to fetch repositories")
        return self._fetch_repositories(token)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_webhook_events(self, selected_events: list[str]) -> list[str]:
        if not selected_events:
            return ["issues", "issue_comment"]

        resolved_events: set[str] = set()
        for trigger in selected_events:
            resolved_events.update(GithubProvider._TRIGGER_EVENTS.get(trigger, [trigger]))

        return sorted(resolved_events) or ["issues"]

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
                except Exception:  # pragma: no cover - fallback path
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
