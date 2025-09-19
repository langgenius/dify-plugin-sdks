import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class LabelTrigger(TriggerEvent):
    """
    GitHub Label Event Trigger

    This unified trigger handles all GitHub label events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub label event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, deleted, edited)
        - label_name_filter: Filter by label names (supports wildcards)
        - label_color_filter: Filter by label colors (hex codes)
        - exclude_default_labels: Exclude default GitHub labels
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

        # Extract label information
        label = payload.get("label", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply label name filter
        label_name_filter = parameters.get("label_name_filter")
        if label_name_filter:
            name_patterns = [n.strip() for n in label_name_filter.split(",") if n.strip()]
            label_name = label.get("name", "")
            name_matched = False
            for pattern in name_patterns:
                if fnmatch.fnmatch(label_name, pattern):
                    name_matched = True
                    break
            if not name_matched:
                raise TriggerIgnoreEventError(
                    f"Label name '{label_name}' doesn't match patterns: {name_patterns}"
                )

        # Apply label color filter
        label_color_filter = parameters.get("label_color_filter")
        if label_color_filter:
            color_patterns = [c.strip().lower() for c in label_color_filter.split(",") if c.strip()]
            label_color = label.get("color", "").lower()
            if label_color not in color_patterns:
                raise TriggerIgnoreEventError(
                    f"Label color '{label_color}' not in allowed colors: {color_patterns}"
                )

        # Apply exclude default labels filter
        exclude_default_labels = parameters.get("exclude_default_labels", False)
        if exclude_default_labels:
            is_default = label.get("default", False)
            if is_default:
                raise TriggerIgnoreEventError("Excluding default GitHub label")

        # Default GitHub labels (common ones)
        default_labels = {
            "bug", "duplicate", "enhancement", "good first issue",
            "help wanted", "invalid", "question", "wontfix"
        }

        # Additional check for common default label names if default field is not available
        if exclude_default_labels and not label.get("default"):
            label_name = label.get("name", "").lower()
            if label_name in default_labels:
                raise TriggerIgnoreEventError(f"Excluding suspected default label: {label_name}")

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "name" in changes:
                changes_info["name"] = {"from": changes["name"].get("from", "")}
            if "description" in changes:
                changes_info["description"] = {"from": changes["description"].get("from", "")}
            if "color" in changes:
                changes_info["color"] = {"from": changes["color"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "label": {
                "id": label.get("id"),
                "name": label.get("name", ""),
                "description": label.get("description", ""),
                "color": label.get("color", ""),
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

        # Add changes info if present
        if changes_info:
            variables["changes"] = changes_info

        return Event(variables=variables)