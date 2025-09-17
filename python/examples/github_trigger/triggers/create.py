from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class CreateTrigger(TriggerEvent):
    """
    GitHub Create Event Trigger

    This trigger handles GitHub create events (branch/tag creation) and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub create event trigger

        Parameters:
        - ref_type_filter: Filter by ref type (branch, tag) (optional)
        - ref_filter: Filter by specific ref name (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract create information
        ref = payload.get("ref", "")
        ref_type = payload.get("ref_type", "")
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply ref type filter if specified
        ref_type_filter = parameters.get("ref_type_filter")
        if ref_type_filter is not None:
            if ref_type != ref_type_filter:
                # Skip this event if it doesn't match the ref type filter
                return Event(variables={})

        # Apply ref filter if specified
        ref_filter = parameters.get("ref_filter")
        if ref_filter is not None:
            if ref != ref_filter:
                # Skip this event if it doesn't match the ref filter
                return Event(variables={})

        # Build variables for the workflow
        variables = {
            "create": {
                "ref": ref,
                "ref_type": ref_type,
                "master_branch": payload.get("master_branch", ""),
                "description": payload.get("description", ""),
                "pusher_type": payload.get("pusher_type", ""),
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "default_branch": repository.get("default_branch", ""),
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