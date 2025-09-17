from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class WatchTrigger(TriggerEvent):
    """
    GitHub Watch Event Trigger

    This trigger handles GitHub watch events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub watch event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a started action (watch events are usually "started")
        action = payload.get("action", "started")
        if action != "started":
            # This trigger only handles started events
            return Event(variables={})

        # Extract repository information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Build variables for the workflow
        variables = {
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "watchers_count": repository.get("watchers_count", 0),
                "stargazers_count": repository.get("stargazers_count", 0),
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