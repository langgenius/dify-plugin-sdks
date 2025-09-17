from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestSynchronizeTrigger(TriggerEvent):
    """
    GitHub Pull Request Synchronize Event Trigger

    This trigger handles GitHub pull request synchronize events (when new commits are pushed)
    and extracts relevant information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request synchronize event trigger

        Parameters:
        - pr_filter: Filter by specific pull request number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a synchronize action
        action = payload.get("action", "")
        if action != "synchronize":
            # This trigger only handles synchronize events
            return Event(variables={})

        # Extract pull request information
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply PR number filter if specified
        pr_filter = parameters.get("pr_filter")
        if pr_filter is not None:
            pr_number = pull_request.get("number")
            if pr_number != int(pr_filter):
                # Skip this event if it doesn't match the PR filter
                return Event(variables={})

        # Build variables for the workflow
        variables = {
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "updated_at": pull_request.get("updated_at", ""),
                "draft": pull_request.get("draft", False),
                "merged": pull_request.get("merged", False),
                "author": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
                },
                "head": {
                    "ref": pull_request.get("head", {}).get("ref", ""),
                    "sha": pull_request.get("head", {}).get("sha", ""),
                    "repo_name": pull_request.get("head", {}).get("repo", {}).get("full_name", ""),
                },
                "base": {
                    "ref": pull_request.get("base", {}).get("ref", ""),
                    "sha": pull_request.get("base", {}).get("sha", ""),
                    "repo_name": pull_request.get("base", {}).get("repo", {}).get("full_name", ""),
                },
            },
            "before": payload.get("before", ""),
            "after": payload.get("after", ""),
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