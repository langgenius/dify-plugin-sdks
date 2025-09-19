from collections.abc import Mapping
from datetime import datetime
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent

from .filters import check_label_match, parse_comma_list


class IssueClosedTrigger(TriggerEvent):
    """
    GitHub Issue Closed Event Trigger
    
    This trigger handles GitHub issue closed events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue closed event trigger with practical filtering

        Parameters:
        - labels: Filter by issue labels
        - closed_by: Filter by who closed the issue
        - resolution_time_max: Maximum resolution time in hours
        - exclude_not_planned: Exclude issues closed as 'not planned'
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")
        
        # Verify this is a closed action
        action = payload.get("action", "")
        if action != "closed":
            # This trigger only handles closed events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'closed'")
        
        # Extract issue information
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        
        # Check if issue was closed as 'not planned'
        exclude_not_planned = parameters.get("exclude_not_planned", False)
        if exclude_not_planned:
            state_reason = issue.get("state_reason", "")
            if state_reason == "not_planned":
                raise TriggerIgnoreEventError("Issue closed as 'not planned'")

        # Label filtering
        labels_filter = parameters.get("labels", "")
        if labels_filter:
            required_labels = parse_comma_list(labels_filter)
            if required_labels:
                issue_labels = issue.get("labels", [])
                if not check_label_match(issue_labels, required_labels):
                    raise TriggerIgnoreEventError(
                        f"Issue doesn't have any of the required labels: {', '.join(required_labels)}"
                    )

        # Closed by filtering
        closed_by_filter = parameters.get("closed_by", "")
        if closed_by_filter:
            allowed_users = parse_comma_list(closed_by_filter)
            if allowed_users:
                closer = sender.get("login", "")  # The sender is who closed it
                if closer not in allowed_users:
                    raise TriggerIgnoreEventError(
                        f"Issue closed by '{closer}' who is not in allowed list: {', '.join(allowed_users)}"
                    )

        # Resolution time filtering
        resolution_time_max = parameters.get("resolution_time_max")
        if resolution_time_max is not None:
            try:
                max_hours = float(resolution_time_max)
                created_at = issue.get("created_at", "")
                closed_at = issue.get("closed_at", "")
                if created_at and closed_at:
                    try:
                        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        closed = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                        resolution_hours = (closed - created).total_seconds() / 3600

                        if resolution_hours > max_hours:
                            raise TriggerIgnoreEventError(
                                f"Issue took {resolution_hours:.1f} hours to resolve, exceeds limit of {max_hours} hours"
                            )
                    except (ValueError, TypeError):
                        pass  # Unable to parse dates, skip filtering
            except ValueError:
                pass  # Invalid max_hours value, skip filtering
        
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
                "closed_at": issue.get("closed_at", ""),
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