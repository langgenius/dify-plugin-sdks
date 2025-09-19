from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueUnassignedTrigger(TriggerEvent):
    """
    GitHub Issue Unassigned Event Trigger
    
    This trigger handles GitHub issue unassigned events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue unassigned event trigger
        
        Parameters:
        - issue_filter: Filter by specific issue number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")
        
        # Verify this is an unassigned action
        action = payload.get("action", "")
        if action != "unassigned":
            # This trigger only handles unassigned events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'unassigned\'")
        
        # Extract issue information
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        assignee = payload.get("assignee", {})
        
        # Apply issue number filter if specified
        issue_filter = parameters.get("issue_filter")
        if issue_filter is not None:
            issue_number = issue.get("number")
            if issue_number != int(issue_filter):
                # Skip this event if it doesn't match the issue filter
                raise TriggerIgnoreEventError("Event does not match filter criteria")
        
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
                        "login": assignee_item.get("login", ""),
                        "avatar_url": assignee_item.get("avatar_url", ""),
                        "html_url": assignee_item.get("html_url", ""),
                    }
                    for assignee_item in issue.get("assignees", [])
                ],
                "author": {
                    "login": issue.get("user", {}).get("login", ""),
                    "avatar_url": issue.get("user", {}).get("avatar_url", ""),
                    "html_url": issue.get("user", {}).get("html_url", ""),
                },
            },
            "assignee": {
                "login": assignee.get("login", ""),
                "avatar_url": assignee.get("avatar_url", ""),
                "html_url": assignee.get("html_url", ""),
                "type": assignee.get("type", ""),
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