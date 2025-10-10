import re
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class IssueUnlabeledEvent(Event):
    """
    GitHub Issue Unlabeled Event

    This event transforms GitHub issue unlabeled webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    The payload includes a 'label' object with the label that was removed.
    """

    def _check_removed_label(self, payload: Mapping[str, Any], removed_label_param: str | None) -> None:
        """Check if the removed label matches the allowed labels"""
        if not removed_label_param:
            return

        allowed_labels = [label.strip() for label in removed_label_param.split(",") if label.strip()]
        if not allowed_labels:
            return

        # The payload contains the label that was removed
        label = payload.get("label", {})
        label_name = label.get("name", "")

        if label_name not in allowed_labels:
            raise EventIgnoreError()

    def _check_title_pattern(self, issue: Mapping[str, Any], pattern: str | None) -> None:
        """Check if issue title matches the pattern"""
        if not pattern:
            return

        title = issue.get("title", "")
        if not re.match(pattern, title):
            raise EventIgnoreError()

    def _check_unlabeler(self, payload: Mapping[str, Any], unlabeler_param: str | None) -> None:
        """Check if the user who removed the label is in allowed list"""
        if not unlabeler_param:
            return

        allowed_unlabelers = [unlabeler.strip() for unlabeler in unlabeler_param.split(",") if unlabeler.strip()]
        if not allowed_unlabelers:
            return

        unlabeler = payload.get("sender", {}).get("login")
        if unlabeler not in allowed_unlabelers:
            raise EventIgnoreError()

    def _check_milestone(self, issue: Mapping[str, Any], milestone_param: str | None) -> None:
        """Check if issue milestone matches allowed milestones"""
        if not milestone_param:
            return

        allowed_milestones = [milestone.strip() for milestone in milestone_param.split(",") if milestone.strip()]
        if not allowed_milestones:
            return

        milestone = issue.get("milestone")
        if not milestone:
            raise EventIgnoreError()

        milestone_title = milestone.get("title")
        if not milestone_title or milestone_title not in allowed_milestones:
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue unlabeled webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_removed_label(payload, parameters.get("removed_label"))
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_unlabeler(payload, parameters.get("unlabeler"))
        self._check_milestone(issue, parameters.get("milestone"))

        return Variables(variables={**payload})
