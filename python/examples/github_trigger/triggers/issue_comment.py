from collections.abc import Mapping
from typing import Any

from utils.dynamic_options import fetch_repositories
from werkzeug import Request

from dify_plugin.entities import ParameterOption
from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueCommentTrigger(TriggerEvent):
    """
    GitHub Issue Comment Event Trigger

    This trigger handles GitHub issue comment events and extracts relevant information
    from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue comment event trigger

        Parameters:
        - action_filter: Filter by action type (created, edited, deleted, or any)
        - issue_filter: Filter by specific issue number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Extract action type
        action = payload.get("action", "")

        # Apply action filter if specified
        action_filter = parameters.get("action_filter", "any")
        if action_filter not in ("any", action):
            # Skip this event if it doesn't match the filter
            return Event(variables={})

        # Extract issue comment information
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply issue number filter if specified
        issue_filter = parameters.get("issue_filter")
        if issue_filter is not None:
            issue_number = issue.get("number")
            if issue_number != int(issue_filter):
                # Skip this event if it doesn't match the issue filter
                return Event(variables={})

        # Check if this is a pull request
        is_pull_request = "pull_request" in issue

        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in issue.get("labels", [])
        ]

        # Build variables for the workflow
        variables = {
            "action": action,
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", ""),
                "html_url": comment.get("html_url", ""),
                "created_at": comment.get("created_at", ""),
                "updated_at": comment.get("updated_at", ""),
                "author": {
                    "login": comment.get("user", {}).get("login", ""),
                    "avatar_url": comment.get("user", {}).get("avatar_url", ""),
                    "html_url": comment.get("user", {}).get("html_url", ""),
                },
            },
            "issue": {
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "html_url": issue.get("html_url", ""),
                "body": issue.get("body", ""),
                "labels": labels,
                "is_pull_request": is_pull_request,
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "closed_at": issue.get("closed_at"),
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in issue.get("assignees", [])
                ],
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

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter == "repository":
            return fetch_repositories(self.runtime.credentials.get("access_tokens"))

        return []
