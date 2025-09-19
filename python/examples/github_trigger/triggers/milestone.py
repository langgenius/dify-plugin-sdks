import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class MilestoneTrigger(TriggerEvent):
    """
    GitHub Milestone Event Trigger

    This unified trigger handles all GitHub milestone events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub milestone event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, deleted, edited, opened, closed)
        - milestone_title_filter: Filter by milestone titles (supports wildcards)
        - milestone_state_filter: Filter by milestone state (open, closed)
        - due_date_filter: Filter by due date presence (has_due_date, no_due_date)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Get the action type
        action = payload.get("action", "")

        # Apply action filter
        action_filter = parameters.get("action_filter", [])
        if action_filter and action not in action_filter:
            raise TriggerIgnoreEventError(
                f"Action '{action}' not in filter list: {action_filter}"
            )

        # Extract milestone information
        milestone = payload.get("milestone", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply milestone title filter
        milestone_title_filter = parameters.get("milestone_title_filter")
        if milestone_title_filter:
            title_patterns = [t.strip() for t in milestone_title_filter.split(",") if t.strip()]
            milestone_title = milestone.get("title", "")
            title_matched = False
            for pattern in title_patterns:
                if fnmatch.fnmatch(milestone_title, pattern):
                    title_matched = True
                    break
            if not title_matched:
                raise TriggerIgnoreEventError(
                    f"Milestone title '{milestone_title}' doesn't match patterns: {title_patterns}"
                )

        # Apply milestone state filter
        milestone_state_filter = parameters.get("milestone_state_filter")
        if milestone_state_filter:
            milestone_state = milestone.get("state", "")
            if milestone_state != milestone_state_filter:
                raise TriggerIgnoreEventError(
                    f"Milestone state '{milestone_state}' doesn't match required state '{milestone_state_filter}'"
                )

        # Apply due date filter
        due_date_filter = parameters.get("due_date_filter")
        if due_date_filter:
            due_on = milestone.get("due_on")
            if due_date_filter == "has_due_date" and not due_on:
                raise TriggerIgnoreEventError("Milestone has no due date")
            elif due_date_filter == "no_due_date" and due_on:
                raise TriggerIgnoreEventError("Milestone has a due date")

        # Extract creator information
        creator = None
        if milestone.get("creator"):
            creator = {
                "login": milestone["creator"].get("login", ""),
                "avatar_url": milestone["creator"].get("avatar_url", ""),
                "html_url": milestone["creator"].get("html_url", ""),
            }

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "title" in changes:
                changes_info["title"] = {"from": changes["title"].get("from", "")}
            if "description" in changes:
                changes_info["description"] = {"from": changes["description"].get("from", "")}
            if "due_on" in changes:
                changes_info["due_on"] = {"from": changes["due_on"].get("from", "")}
            if "state" in changes:
                changes_info["state"] = {"from": changes["state"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "milestone": {
                "id": milestone.get("id"),
                "number": milestone.get("number"),
                "title": milestone.get("title", ""),
                "description": milestone.get("description", ""),
                "state": milestone.get("state", ""),
                "html_url": milestone.get("html_url", ""),
                "created_at": milestone.get("created_at", ""),
                "updated_at": milestone.get("updated_at", ""),
                "due_on": milestone.get("due_on", ""),
                "closed_at": milestone.get("closed_at", ""),
                "creator": creator,
                "open_issues": milestone.get("open_issues", 0),
                "closed_issues": milestone.get("closed_issues", 0),
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

        # Add changes info if present
        if changes_info:
            variables["changes"] = changes_info

        return Event(variables=variables)