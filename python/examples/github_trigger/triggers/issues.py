from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssuesTrigger(TriggerEvent):
    """
    GitHub Issue Event Trigger

    This unified trigger handles all GitHub issue events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue event trigger with comprehensive filtering

        Parameters:
        - event: Select which issue actions to trigger on (opened, closed, reopened, edited, assigned, labeled, etc.)
        - labels: Only trigger if issue has these labels (comma-separated)
        - exclude_labels: Don't trigger if issue has these labels (comma-separated)
        - assignee: Only trigger if assigned to these users (comma-separated)
        - authors: Only trigger for issues from these authors (comma-separated)
        - exclude_authors: Don't trigger for issues from these authors (comma-separated)
        - milestone: Only trigger for issues with these milestones (comma-separated)
        - title_pattern: Only trigger if title matches this pattern (supports wildcards, comma-separated)
        - body_contains: Only trigger if body contains these keywords (comma-separated)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Get the action type
        action = payload.get("action", "")

        # Apply event filter
        event = parameters.get("event", [])
        if event and action not in event:
            raise TriggerIgnoreEventError(f"Action '{action}' not in filter list: {event}")

        return Event(
            variables={
                "action": action,
            }
        )
