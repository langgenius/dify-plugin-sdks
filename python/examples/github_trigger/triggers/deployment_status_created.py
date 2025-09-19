import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class DeploymentStatusCreatedTrigger(TriggerEvent):
    """
    GitHub DeploymentStatusCreated Event Trigger

    This trigger handles GitHub deployment status created events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub deployment status created event trigger with practical filtering

        Parameters:
        - environments: Filter by deployment environments (comma-separated, supports wildcards)
        - states: Filter by deployment status states (comma-separated)
        - exclude_actors: Exclude deployments by these actors (comma-separated)
        - target_urls: Filter by target URL patterns (comma-separated, supports wildcards)
        - failure_only: Only trigger for failed deployments
        - production_only: Only trigger for production deployments
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract deployment status and deployment information
        deployment_status = payload.get("deployment_status", {})
        deployment = payload.get("deployment", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Environment filtering
        environments_filter = parameters.get("environments", "")
        if environments_filter:
            allowed_envs = [e.strip() for e in environments_filter.split(",") if e.strip()]
            if allowed_envs:
                environment = deployment.get("environment", "")
                env_matched = False
                for pattern in allowed_envs:
                    if fnmatch.fnmatch(environment, pattern):
                        env_matched = True
                        break
                if not env_matched:
                    raise TriggerIgnoreEventError(
                        f"Deployment environment '{environment}' doesn't match allowed patterns: {', '.join(allowed_envs)}"
                    )

        # State filtering
        states_filter = parameters.get("states", "")
        if states_filter:
            allowed_states = [s.strip() for s in states_filter.split(",") if s.strip()]
            if allowed_states:
                state = deployment_status.get("state", "")
                if state not in allowed_states:
                    raise TriggerIgnoreEventError(
                        f"Deployment status '{state}' not in allowed states: {', '.join(allowed_states)}"
                    )

        # Exclude actors filtering
        exclude_actors = parameters.get("exclude_actors", "")
        if exclude_actors:
            excluded = [a.strip() for a in exclude_actors.split(",") if a.strip()]
            if excluded:
                actor = sender.get("login", "")
                if actor in excluded:
                    raise TriggerIgnoreEventError(f"Deployment by excluded actor: {actor}")

        # Target URL filtering
        target_urls_filter = parameters.get("target_urls", "")
        if target_urls_filter:
            allowed_patterns = [p.strip() for p in target_urls_filter.split(",") if p.strip()]
            if allowed_patterns:
                target_url = deployment_status.get("target_url", "")
                url_matched = False
                for pattern in allowed_patterns:
                    if fnmatch.fnmatch(target_url, pattern):
                        url_matched = True
                        break
                if not url_matched and target_url:  # Only filter if target_url exists
                    raise TriggerIgnoreEventError(
                        f"Target URL '{target_url}' doesn't match allowed patterns: {', '.join(allowed_patterns)}"
                    )

        # Failure only filtering
        failure_only = parameters.get("failure_only", False)
        if failure_only:
            state = deployment_status.get("state", "")
            if state not in ["error", "failure"]:
                raise TriggerIgnoreEventError(f"Deployment status '{state}' is not a failure")

        # Production only filtering
        production_only = parameters.get("production_only", False)
        if production_only:
            environment = deployment.get("environment", "").lower()
            if environment not in ["production", "prod"]:
                raise TriggerIgnoreEventError(f"Deployment environment '{environment}' is not production")

        # Build variables for the workflow
        variables = {
            "deployment_status": {
                "id": deployment_status.get("id"),
                "state": deployment_status.get("state", ""),
                "target_url": deployment_status.get("target_url", ""),
                "description": deployment_status.get("description", ""),
                "environment_url": deployment_status.get("environment_url", ""),
                "log_url": deployment_status.get("log_url", ""),
                "created_at": deployment_status.get("created_at", ""),
                "updated_at": deployment_status.get("updated_at", ""),
                "creator": {
                    "login": deployment_status.get("creator", {}).get("login", ""),
                    "avatar_url": deployment_status.get("creator", {}).get("avatar_url", ""),
                    "html_url": deployment_status.get("creator", {}).get("html_url", ""),
                    "type": deployment_status.get("creator", {}).get("type", ""),
                },
            },
            "deployment": {
                "id": deployment.get("id"),
                "sha": deployment.get("sha", ""),
                "ref": deployment.get("ref", ""),
                "task": deployment.get("task", ""),
                "payload": deployment.get("payload", {}),
                "original_environment": deployment.get("original_environment", ""),
                "environment": deployment.get("environment", ""),
                "description": deployment.get("description", ""),
                "creator": {
                    "login": deployment.get("creator", {}).get("login", ""),
                    "avatar_url": deployment.get("creator", {}).get("avatar_url", ""),
                    "html_url": deployment.get("creator", {}).get("html_url", ""),
                    "type": deployment.get("creator", {}).get("type", ""),
                },
                "created_at": deployment.get("created_at", ""),
                "updated_at": deployment.get("updated_at", ""),
                "statuses_url": deployment.get("statuses_url", ""),
                "repository_url": deployment.get("repository_url", ""),
                "transient_environment": deployment.get("transient_environment", False),
                "production_environment": deployment.get("production_environment", False),
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "owner": {
                    "login": repository.get("owner", {}).get("login", ""),
                    "avatar_url": repository.get("owner", {}).get("avatar_url", ""),
                    "html_url": repository.get("owner", {}).get("html_url", ""),
                },
            },
            "sender": {
                "login": sender.get("login", ""),
                "avatar_url": sender.get("avatar_url", ""),
                "html_url": sender.get("html_url", ""),
                "type": sender.get("type", ""),
            },
        }

        return Event(variables=variables)
