from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class StarCreatedTrigger(TriggerEvent):
    """
    GitHub Star Created Event Trigger

    This trigger handles GitHub star created events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub star created event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a created action
        action = payload.get("action", "")
        if action != "created":
            # This trigger only handles created events
            return Event(variables={})

        # Extract information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        starred_at = payload.get("starred_at", "")

        # Build variables for the workflow
        variables = {
            "star": {
                "starred_at": starred_at,
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "stargazers_count": repository.get("stargazers_count", 0),
                "watchers_count": repository.get("watchers_count", 0),
                "forks_count": repository.get("forks_count", 0),
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