from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class RepositoryEditedTrigger(TriggerEvent):
    """
    GitHub Repository Repository Edited Event Trigger

    This trigger handles GitHub repository edited events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub repository edited event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a edited action
        action = payload.get("action", "")
        if action != "edited":
            # This trigger only handles edited events
            return Event(variables={})

        # Extract repository information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Build variables for the workflow
        variables = {
            "repository": {
                "id": repository.get("id"),
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "archived": repository.get("archived", False),
                "disabled": repository.get("disabled", False),
                "default_branch": repository.get("default_branch", ""),
                "topics": repository.get("topics", []),
                "language": repository.get("language", ""),
                "size": repository.get("size", 0),
                "stargazers_count": repository.get("stargazers_count", 0),
                "watchers_count": repository.get("watchers_count", 0),
                "forks_count": repository.get("forks_count", 0),
                "open_issues_count": repository.get("open_issues_count", 0),
                "created_at": repository.get("created_at", ""),
                "updated_at": repository.get("updated_at", ""),
                "pushed_at": repository.get("pushed_at", ""),
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