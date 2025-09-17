from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class PushTrigger(TriggerEvent):
    """
    GitHub Push Event Trigger

    This trigger handles GitHub push events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub push event trigger

        Parameters:
        - branch_filter: Filter by specific branch name (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract push information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        ref = payload.get("ref", "")
        branch_name = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

        # Apply branch filter if specified
        branch_filter = parameters.get("branch_filter")
        if branch_filter is not None:
            if branch_name != branch_filter:
                # Skip this event if it doesn't match the branch filter
                return Event(variables={})

        # Extract commits information
        commits = []
        for commit in payload.get("commits", []):
            commits.append({
                "id": commit.get("id", ""),
                "message": commit.get("message", ""),
                "timestamp": commit.get("timestamp", ""),
                "url": commit.get("url", ""),
                "author": {
                    "name": commit.get("author", {}).get("name", ""),
                    "email": commit.get("author", {}).get("email", ""),
                    "username": commit.get("author", {}).get("username", ""),
                },
                "committer": {
                    "name": commit.get("committer", {}).get("name", ""),
                    "email": commit.get("committer", {}).get("email", ""),
                    "username": commit.get("committer", {}).get("username", ""),
                },
                "added": commit.get("added", []),
                "removed": commit.get("removed", []),
                "modified": commit.get("modified", []),
            })

        # Build variables for the workflow
        variables = {
            "push": {
                "ref": ref,
                "branch": branch_name,
                "before": payload.get("before", ""),
                "after": payload.get("after", ""),
                "created": payload.get("created", False),
                "deleted": payload.get("deleted", False),
                "forced": payload.get("forced", False),
                "commits": commits,
                "head_commit": {
                    "id": payload.get("head_commit", {}).get("id", ""),
                    "message": payload.get("head_commit", {}).get("message", ""),
                    "timestamp": payload.get("head_commit", {}).get("timestamp", ""),
                    "url": payload.get("head_commit", {}).get("url", ""),
                    "author": {
                        "name": payload.get("head_commit", {}).get("author", {}).get("name", ""),
                        "email": payload.get("head_commit", {}).get("author", {}).get("email", ""),
                        "username": payload.get("head_commit", {}).get("author", {}).get("username", ""),
                    },
                },
                "compare": payload.get("compare", ""),
                "size": len(commits),
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