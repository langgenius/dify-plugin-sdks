from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.interfaces.trigger import Trigger
from dify_plugin.entities.trigger import TriggerEvent


class PushTrigger(Trigger):
    """
    GitHub Push Event Trigger

    This trigger handles GitHub push events and extracts relevant information
    from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, values: Mapping[str, Any], parameters: Mapping[str, Any]) -> TriggerEvent:
        """
        Handle GitHub push event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract push event information
        repository = payload.get("repository", {})
        pusher = payload.get("pusher", {})
        commits = payload.get("commits", [])
        ref = payload.get("ref", "")

        # Extract branch name from ref (refs/heads/main -> main)
        branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else ref

        # Build variables for the workflow
        variables = {
            "repository_name": repository.get("name", ""),
            "repository_full_name": repository.get("full_name", ""),
            "repository_url": repository.get("html_url", ""),
            "branch": branch,
            "ref": ref,
            "pusher_name": pusher.get("name", ""),
            "pusher_email": pusher.get("email", ""),
            "commits_count": len(commits),
            "commits": [
                {
                    "id": commit.get("id", ""),
                    "message": commit.get("message", ""),
                    "author": {
                        "name": commit.get("author", {}).get("name", ""),
                        "email": commit.get("author", {}).get("email", ""),
                    },
                    "url": commit.get("url", ""),
                    "added": commit.get("added", []),
                    "removed": commit.get("removed", []),
                    "modified": commit.get("modified", []),
                }
                for commit in commits
            ],
            "head_commit": None,
        }

        # Add head commit information if available
        head_commit = payload.get("head_commit")
        if head_commit:
            variables["head_commit"] = {
                "id": head_commit.get("id", ""),
                "message": head_commit.get("message", ""),
                "author": {
                    "name": head_commit.get("author", {}).get("name", ""),
                    "email": head_commit.get("author", {}).get("email", ""),
                },
                "url": head_commit.get("url", ""),
                "added": head_commit.get("added", []),
                "removed": head_commit.get("removed", []),
                "modified": head_commit.get("modified", []),
            }

        return TriggerEvent(variables=variables)
