from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueCommentEditedTrigger(TriggerEvent):
    """
    GitHub Issue Comment Edited Event Trigger
    
    This trigger handles GitHub issue comment edit events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue comment edited event trigger
        
        Parameters:
        - issue_filter: Filter by specific issue number (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")
        
        # Verify this is an edited action
        action = payload.get("action", "")
        if action != "edited":
            # This trigger only handles edited events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'edited\'")
        
        # Extract issue comment information
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})
        
        # Apply issue number filter if specified
        issue_filter = parameters.get("issue_filter")
        if issue_filter is not None:
            issue_number = issue.get("number")
            if issue_number != int(issue_filter):
                # Skip this event if it doesn't match the issue filter
                raise TriggerIgnoreEventError("Event does not match filter criteria")
        
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
        
        # Extract the previous body from changes if available
        body_from = ""
        if changes and "body" in changes:
            body_from = changes["body"].get("from", "")
        
        # Build variables for the workflow
        variables = {
            "comment": {
                "id": comment.get("id"),
                "body": comment.get("body", ""),
                "body_from": body_from,
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