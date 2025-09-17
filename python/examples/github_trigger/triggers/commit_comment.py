from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class CommitCommentTrigger(TriggerEvent):
    """
    GitHub Commit Comment Event Trigger

    This trigger handles GitHub commit comment events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub commit comment event trigger

        Parameters:
        - commit_filter: Filter by specific commit SHA (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # This event only has 'created' action, but let's verify it's present
        action = payload.get("action", "created")
        if action != "created":
            # This trigger only handles created events
            return Event(variables={})

        # Extract comment and repository information
        comment = payload.get("comment", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply commit filter if specified
        commit_filter = parameters.get("commit_filter")
        if commit_filter:
            commit_id = comment.get("commit_id", "")
            if not commit_id.startswith(commit_filter):
                # Skip this event if it doesn't match the commit filter
                return Event(variables={})

        # Build variables for the workflow
        variables = {
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", ""),
                "html_url": comment.get("html_url", ""),
                "created_at": comment.get("created_at", ""),
                "updated_at": comment.get("updated_at", ""),
                "line": comment.get("line"),
                "path": comment.get("path", ""),
                "position": comment.get("position"),
                "commit_id": comment.get("commit_id", ""),
                "author": {
                    "login": comment.get("user", {}).get("login", ""),
                    "avatar_url": comment.get("user", {}).get("avatar_url", ""),
                    "html_url": comment.get("user", {}).get("html_url", ""),
                },
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