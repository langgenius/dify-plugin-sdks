from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueUnlabeledTrigger(TriggerEvent):
    """
    GitHub Issue Unlabeled Event Trigger
    
    This trigger handles GitHub issue unlabeled events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue unlabeled event trigger
        
        Parameters:
        - issue_filter: Filter by specific issue number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")
        
        # Verify this is an unlabeled action
        action = payload.get("action", "")
        if action != "unlabeled":
            # This trigger only handles unlabeled events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'unlabeled\'")
        
        # Extract issue information
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        label = payload.get("label", {})
        
        # Apply issue number filter if specified
        issue_filter = parameters.get("issue_filter")
        if issue_filter is not None:
            issue_number = issue.get("number")
            if issue_number != int(issue_filter):
                # Skip this event if it doesn't match the issue filter
                raise TriggerIgnoreEventError("Event does not match filter criteria")
        
        # Extract remaining labels
        labels = [
            {
                "name": label_item.get("name", ""),
                "color": label_item.get("color", ""),
                "description": label_item.get("description", ""),
            }
            for label_item in issue.get("labels", [])
        ]
        
        # Build variables for the workflow
        variables = {
            "issue": {
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "state": issue.get("state", ""),
                "html_url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "labels": labels,
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in issue.get("assignees", [])
                ],
                "author": {
                    "login": issue.get("user", {}).get("login", ""),
                    "avatar_url": issue.get("user", {}).get("avatar_url", ""),
                    "html_url": issue.get("user", {}).get("html_url", ""),
                },
            },
            "label": {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
                "default": label.get("default", False),
                "url": label.get("url", ""),
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