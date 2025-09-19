from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestReadyForReviewTrigger(TriggerEvent):
    """
    GitHub Pull Request Ready for Review Event Trigger

    This trigger handles GitHub pull request ready for review events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request ready for review event trigger

        Parameters:
        - pr_filter: Filter by specific PR number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a ready_for_review action
        action = payload.get("action", "")
        if action != "ready_for_review":
            # This trigger only handles ready_for_review events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'ready_for_review\'")

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
                raise TriggerIgnoreEventError("Event does not match filter criteria")

        # Build variables for the workflow
        variables = {
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "draft": pull_request.get("draft", False),
                "head": {
                    "ref": pull_request.get("head", {}).get("ref", ""),
                    "sha": pull_request.get("head", {}).get("sha", ""),
                },
                "base": {
                    "ref": pull_request.get("base", {}).get("ref", ""),
                    "sha": pull_request.get("base", {}).get("sha", ""),
                },
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