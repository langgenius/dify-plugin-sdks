from collections.abc import Mapping
import re
from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class IssueClosedEvent(Event):
    """
    GitHub Issue Closed Event

    This event transforms GitHub issue closed webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _check_state_reason(self, issue: Mapping[str, Any], state_reason_param: str | None) -> None:
        """Check if issue close reason matches allowed reasons"""
        if not state_reason_param:
            return

        allowed_reasons = [reason.strip() for reason in state_reason_param.split(",") if reason.strip()]
        if not allowed_reasons:
            return

        issue_state_reason = issue.get("state_reason")
        if not issue_state_reason or issue_state_reason not in allowed_reasons:
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

    def _check_closer(self, payload: Mapping[str, Any], closer_param: str | None) -> None:
        """Check if the user who closed the issue is in allowed list"""
        if not closer_param:
            return

        allowed_closers = [closer.strip() for closer in closer_param.split(",") if closer.strip()]
        if not allowed_closers:
            return

        closer = payload.get("sender", {}).get("login")
        if closer not in allowed_closers:
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
        Transform GitHub issue closed webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_state_reason(issue, parameters.get("state_reason"))
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_labels(issue, parameters.get("labels"))
        self._check_closer(payload, parameters.get("closer"))
        self._check_milestone(issue, parameters.get("milestone"))

        return Variables(variables={**payload})
