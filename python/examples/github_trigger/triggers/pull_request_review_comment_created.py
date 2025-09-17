from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestReviewCommentCreatedTrigger(TriggerEvent):
    """
    GitHub Pull Request Review Comment Pull Request Review Comment Created Event Trigger

    This trigger handles GitHub pull request review comment created events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request review comment created event trigger

        Parameters:
        - pr_filter: Filter by specific PR number (optional)
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

        # Extract comment, pull request, and repository information
        comment = payload.get("comment", {})
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
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", ""),
                "html_url": comment.get("html_url", ""),
                "created_at": comment.get("created_at", ""),
                "updated_at": comment.get("updated_at", ""),
                "line": comment.get("line"),
                "path": comment.get("path", ""),
                "diff_hunk": comment.get("diff_hunk", ""),
                "author": {
                    "login": comment.get("user", {}).get("login", ""),
                    "avatar_url": comment.get("user", {}).get("avatar_url", ""),
                    "html_url": comment.get("user", {}).get("html_url", ""),
                },
            },
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "author": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
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