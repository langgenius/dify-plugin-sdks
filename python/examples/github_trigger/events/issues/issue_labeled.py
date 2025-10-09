from collections.abc import Mapping
import re
from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class IssueLabeledEvent(Event):
    """
    GitHub Issue Labeled Event

    This event transforms GitHub issue labeled webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    The payload includes a 'label' object with the label that was added.
    """

    def _check_added_label(self, payload: Mapping[str, Any], added_label_param: str | None) -> None:
        """Check if the added label matches the allowed labels"""
        if not added_label_param:
            return

        allowed_labels = [label.strip() for label in added_label_param.split(",") if label.strip()]
        if not allowed_labels:
            return

        # The payload contains the label that was added
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

    def _check_labeler(self, payload: Mapping[str, Any], labeler_param: str | None) -> None:
        """Check if the user who added the label is in allowed list"""
        if not labeler_param:
            return

        allowed_labelers = [labeler.strip() for labeler in labeler_param.split(",") if labeler.strip()]
        if not allowed_labelers:
            return

        labeler = payload.get("sender", {}).get("login")
        if labeler not in allowed_labelers:
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
        Transform GitHub issue labeled webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_added_label(payload, parameters.get("added_label"))
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_labeler(payload, parameters.get("labeler"))
        self._check_milestone(issue, parameters.get("milestone"))

        return Variables(variables={**payload})
