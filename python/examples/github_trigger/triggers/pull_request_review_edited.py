from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestReviewEditedTrigger(TriggerEvent):
    """
    GitHub Pull Request Review Pull Request Review Edited Event Trigger

    This trigger handles GitHub pull request review edited events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request review edited event trigger

        Parameters:
        - pr_filter: Filter by specific PR number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a edited action
        action = payload.get("action", "")
        if action != "edited":
            # This trigger only handles edited events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'edited\'")

        # Extract review, pull request, and repository information
        review = payload.get("review", {})
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply PR number filter if specified
        pr_filter = parameters.get("pr_filter")
        if pr_filter is not None:
            pr_number = pull_request.get("number")
            if pr_number != int(pr_filter):
                # Skip this event if it doesn't match the PR filter
                raise TriggerIgnoreEventError("Event does not match filter criteria")

        # Build variables for the workflow
        variables = {
            "review": {
                "id": review.get("id"),
                "body": review.get("body", ""),
                "state": review.get("state", ""),
                "html_url": review.get("html_url", ""),
                "submitted_at": review.get("submitted_at", ""),
                "author": {
                    "login": review.get("user", {}).get("login", ""),
                    "avatar_url": review.get("user", {}).get("avatar_url", ""),
                    "html_url": review.get("user", {}).get("html_url", ""),
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