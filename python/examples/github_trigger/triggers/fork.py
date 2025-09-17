from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class ForkTrigger(TriggerEvent):
    """
    GitHub Fork Event Trigger

    This trigger handles GitHub fork events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub fork event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract fork information
        forkee = payload.get("forkee", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Build variables for the workflow
        variables = {
            "fork": {
                "id": forkee.get("id"),
                "name": forkee.get("name", ""),
                "full_name": forkee.get("full_name", ""),
                "html_url": forkee.get("html_url", ""),
                "description": forkee.get("description", ""),
                "private": forkee.get("private", False),
                "created_at": forkee.get("created_at", ""),
                "updated_at": forkee.get("updated_at", ""),
                "clone_url": forkee.get("clone_url", ""),
                "ssh_url": forkee.get("ssh_url", ""),
                "default_branch": forkee.get("default_branch", ""),
                "owner": {
                    "login": forkee.get("owner", {}).get("login", ""),
                    "avatar_url": forkee.get("owner", {}).get("avatar_url", ""),
                    "html_url": forkee.get("owner", {}).get("html_url", ""),
                    "type": forkee.get("owner", {}).get("type", ""),
                },
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "forks_count": repository.get("forks_count", 0),
                "stargazers_count": repository.get("stargazers_count", 0),
                "watchers_count": repository.get("watchers_count", 0),
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