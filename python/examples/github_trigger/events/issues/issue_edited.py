import re
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class IssueEditedEvent(Event):
    """
    GitHub Issue Edited Event

    This event transforms GitHub issue edited webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    The payload includes a 'changes' object showing what was modified.
    """

    def _check_changed_fields(self, payload: Mapping[str, Any], changed_fields_param: str | None) -> None:
        """Check if the edited fields match the allowed fields"""
        if not changed_fields_param:
            return

        allowed_fields = [field.strip() for field in changed_fields_param.split(",") if field.strip()]
        if not allowed_fields:
            return

        changes = payload.get("changes", {})
        if not changes:
            raise EventIgnoreError()

        # Check if any of the changed fields match the allowed fields
        changed_field_names = list(changes.keys())
        if not any(field in changed_field_names for field in allowed_fields):
            raise EventIgnoreError()

    def _check_title_pattern(self, issue: Mapping[str, Any], pattern: str | None) -> None:
        """Check if issue title matches the pattern"""
        if not pattern:
            return

        title = issue.get("title", "")
        if not re.match(pattern, title):
            raise EventIgnoreError()

    def _check_labels(self, issue: Mapping[str, Any], labels_param: str | None) -> None:
        """Check if issue has required labels"""
        if not labels_param:
            return

        required_labels = [label.strip() for label in labels_param.split(",") if label.strip()]
        if not required_labels:
            return

        issue_labels = [label.get("name") for label in issue.get("labels", [])]
        if not any(label in issue_labels for label in required_labels):
            raise EventIgnoreError()

    def _check_editor(self, payload: Mapping[str, Any], editor_param: str | None) -> None:
        """Check if the user who edited the issue is in allowed list"""
        if not editor_param:
            return

        allowed_editors = [editor.strip() for editor in editor_param.split(",") if editor.strip()]
        if not allowed_editors:
            return

        editor = payload.get("sender", {}).get("login")
        if editor not in allowed_editors:
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue edited webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_changed_fields(payload, parameters.get("changed_fields"))
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_labels(issue, parameters.get("labels"))
        self._check_editor(payload, parameters.get("editor"))

        return Variables(variables={**payload})
